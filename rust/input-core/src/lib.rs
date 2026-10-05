//! Experimental Linux-only immutable submitted-ZIP input sessions.
//! Paths locate an initial file descriptor only; accepted bytes are retained in memory.

use caseless::Caseless;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{Cursor, Read};
use std::path::{Component, Path};
use std::time::{Duration, Instant};
use unicode_normalization::UnicodeNormalization;

pub const MAX_ARCHIVE: usize = 16 * 1024 * 1024;
pub const MAX_ENTRIES: usize = 4096;
pub const MAX_FILE: usize = 4 * 1024 * 1024;
pub const MAX_TOTAL: usize = 32 * 1024 * 1024;
pub const MAX_PATH: usize = 1024;
pub const MAX_FRAME: usize = 65536;
pub const MAX_CHUNK: usize = 32768;
pub const MAX_PAGE: usize = 32;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ErrorCode {
    InvalidRequest, InvalidSequence, InvalidState, InvalidPath, InputChanged,
    HashMismatch, LimitExceeded, InvalidArchive, UnsupportedArchive, IoError,
    DeadlineExceeded, InternalError,
}
impl ErrorCode {
    pub fn message(self) -> &'static str {
        match self {
            Self::InvalidRequest => "Invalid request.",
            Self::InvalidSequence => "Invalid request sequence.",
            Self::InvalidState => "Operation is not valid in this session state.",
            Self::InvalidPath => "Input path is not an accepted local regular file.",
            Self::InputChanged => "Input changed while being imported.",
            Self::HashMismatch => "Input bytes do not match the expected SHA256.",
            Self::LimitExceeded => "Input or request exceeds a configured limit.",
            Self::InvalidArchive => "Input is not an accepted ZIP archive.",
            Self::UnsupportedArchive => "ZIP feature is outside the accepted profile.",
            Self::IoError => "Input or transport operation failed.",
            Self::DeadlineExceeded => "Session deadline exceeded.",
            Self::InternalError => "Input session failed.",
        }
    }
}
pub type Result<T> = std::result::Result<T, ErrorCode>;

#[derive(Debug, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Request {
    OpenImport { protocol: u32, seq: u64, path: String, expected_sha256: String },
    Entries { protocol: u32, seq: u64, offset: usize, limit: usize },
    ReadEntry { protocol: u32, seq: u64, entry_id: usize, offset: usize, limit: usize },
    Close { protocol: u32, seq: u64 },
}
impl Request {
    pub fn protocol_seq(&self) -> (u32, u64) {
        match self {
            Self::OpenImport { protocol, seq, .. } | Self::Entries { protocol, seq, .. }
            | Self::ReadEntry { protocol, seq, .. } | Self::Close { protocol, seq } => (*protocol, *seq),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct EntryInfo {
    pub entry_id: usize,
    pub path: String,
    pub size_bytes: usize,
    pub raw_sha256: String,
}
struct Entry { info: EntryInfo, bytes: Box<[u8]> }
#[derive(Debug, Serialize)]
pub struct ImportInfo {
    pub input_sha256: String,
    pub entries_count: usize,
    pub files_count: usize,
    pub total_bytes: usize,
}
pub struct Session {
    // Keep the original no-follow leaf FD open until close/drop. No path is reopened.
    _source: File,
    info: ImportInfo,
    entries: Vec<Entry>,
}
impl Session {
    #[cfg(target_os = "linux")]
    pub fn open(path: &Path, expected_sha256: &str) -> Result<Self> {
        let deadline = Instant::now() + Duration::from_secs(10);
        if expected_sha256.len() != 64 || !expected_sha256.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) {
            return Err(ErrorCode::InvalidRequest);
        }
        let mut source = open_nofollow(path)?;
        let before = stamp(&source)?;
        if before.size > MAX_ARCHIVE as u64 { return Err(ErrorCode::LimitExceeded); }
        let mut bytes = Vec::with_capacity(before.size as usize);
        let mut scratch = [0u8; 65536];
        loop {
            check_deadline(deadline)?;
            let n = source.read(&mut scratch).map_err(|_| ErrorCode::IoError)?;
            if n == 0 { break; }
            if bytes.len().checked_add(n).ok_or(ErrorCode::LimitExceeded)? > MAX_ARCHIVE { return Err(ErrorCode::LimitExceeded); }
            bytes.extend_from_slice(&scratch[..n]);
        }
        if before != stamp(&source)? || bytes.len() as u64 != before.size { return Err(ErrorCode::InputChanged); }
        let input_sha256 = sha256(&bytes);
        if input_sha256 != expected_sha256 { return Err(ErrorCode::HashMismatch); }
        let (entries, entries_count, total_bytes) = import_bytes(&bytes, deadline)?;
        let info = ImportInfo { input_sha256, entries_count, files_count: entries.len(), total_bytes };
        Ok(Self { _source: source, info, entries })
    }
    pub fn info(&self) -> &ImportInfo { &self.info }
    pub fn entries(&self, offset: usize, limit: usize) -> Result<(Vec<&EntryInfo>, Option<usize>)> {
        if limit == 0 || limit > MAX_PAGE || offset > self.entries.len() { return Err(ErrorCode::InvalidRequest); }
        let target = offset.saturating_add(limit).min(self.entries.len());
        let mut end = offset;
        let mut encoded = 0;
        while end < target {
            encoded += serde_json::to_vec(&self.entries[end].info).map_err(|_| ErrorCode::InternalError)?.len() + 1;
            if encoded > 60 * 1024 { break; }
            end += 1;
        }
        Ok((self.entries[offset..end].iter().map(|e| &e.info).collect(), (end < self.entries.len()).then_some(end)))
    }
    pub fn read_entry(&self, entry_id: usize, offset: usize, limit: usize) -> Result<(&EntryInfo, &[u8], Option<usize>)> {
        let entry = self.entries.get(entry_id).ok_or(ErrorCode::InvalidRequest)?;
        if limit == 0 || limit > MAX_CHUNK || offset > entry.bytes.len() { return Err(ErrorCode::InvalidRequest); }
        let end = offset.saturating_add(limit).min(entry.bytes.len());
        Ok((&entry.info, &entry.bytes[offset..end], (end < entry.bytes.len()).then_some(end)))
    }
}
pub fn sha256(bytes: &[u8]) -> String { format!("{:x}", Sha256::digest(bytes)) }
fn check_deadline(deadline: Instant) -> Result<()> {
    if Instant::now() >= deadline { Err(ErrorCode::DeadlineExceeded) } else { Ok(()) }
}

#[cfg(target_os = "linux")]
#[derive(Debug, PartialEq, Eq)]
struct Stamp { dev: u64, ino: u64, size: u64, mode: u32, nlink: u64, mtime: i64, mtime_nsec: i64, ctime: i64, ctime_nsec: i64 }
#[cfg(target_os = "linux")]
fn stamp(file: &File) -> Result<Stamp> {
    use std::os::unix::fs::MetadataExt;
    let m = file.metadata().map_err(|_| ErrorCode::IoError)?;
    if !m.is_file() || m.nlink() != 1 { return Err(ErrorCode::InvalidPath); }
    Ok(Stamp { dev: m.dev(), ino: m.ino(), size: m.size(), mode: m.mode(), nlink: m.nlink(), mtime: m.mtime(), mtime_nsec: m.mtime_nsec(), ctime: m.ctime(), ctime_nsec: m.ctime_nsec() })
}
#[cfg(target_os = "linux")]
fn open_nofollow(path: &Path) -> Result<File> {
    use rustix::fs::{open, openat, Mode, OFlags};
    use std::os::unix::ffi::OsStrExt;
    // Reject rather than normalize dot components, repeated separators, and trailing slash.
    let raw = path.as_os_str().as_bytes();
    if raw.len() > 4096 || raw.first() != Some(&b'/') || raw.ends_with(b"/") || raw.contains(&0)
        || raw[1..].split(|b| *b == b'/').any(|p| p.is_empty() || p == b"." || p == b"..") {
        return Err(ErrorCode::InvalidPath);
    }
    let mut parts = path.components();
    if parts.next() != Some(Component::RootDir) { return Err(ErrorCode::InvalidPath); }
    let parts: Vec<_> = parts.collect();
    if parts.is_empty() { return Err(ErrorCode::InvalidPath); }
    let dirflags = OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC;
    let mut dir = open("/", dirflags, Mode::empty()).map_err(|_| ErrorCode::InvalidPath)?;
    for p in &parts[..parts.len() - 1] {
        let Component::Normal(p) = p else { return Err(ErrorCode::InvalidPath); };
        dir = openat(&dir, *p, dirflags, Mode::empty()).map_err(|_| ErrorCode::InvalidPath)?;
    }
    let Component::Normal(leaf) = parts[parts.len() - 1] else { return Err(ErrorCode::InvalidPath); };
    let fd = openat(&dir, leaf, OFlags::RDONLY | OFlags::NONBLOCK | OFlags::NOFOLLOW | OFlags::CLOEXEC, Mode::empty()).map_err(|_| ErrorCode::InvalidPath)?;
    let file = File::from(fd);
    stamp(&file)?;
    Ok(file)
}

#[derive(Debug)]
struct Member {
    path: String, directory: bool, method: u16, crc: u32,
    compressed: usize, size: usize, local: usize, central: usize, data: usize, end: usize,
}
fn u16at(b: &[u8], p: usize) -> Result<u16> {
    let v = b.get(p..p.checked_add(2).ok_or(ErrorCode::InvalidArchive)?).ok_or(ErrorCode::InvalidArchive)?;
    Ok(u16::from_le_bytes([v[0], v[1]]))
}
fn u32at(b: &[u8], p: usize) -> Result<u32> {
    let v = b.get(p..p.checked_add(4).ok_or(ErrorCode::InvalidArchive)?).ok_or(ErrorCode::InvalidArchive)?;
    Ok(u32::from_le_bytes([v[0], v[1], v[2], v[3]]))
}
fn extra_fields(extra: &[u8]) -> Result<()> {
    let mut p = 0;
    while p < extra.len() {
        let id = u16at(extra, p)?;
        let n = u16at(extra, p + 2)? as usize;
        p = p.checked_add(4 + n).ok_or(ErrorCode::InvalidArchive)?;
        if p > extra.len() { return Err(ErrorCode::InvalidArchive); }
        // ZIP64, AES and alternate Unicode-path metadata are outside this profile.
        if matches!(id, 0x0001 | 0x9901 | 0x7075) { return Err(ErrorCode::UnsupportedArchive); }
    }
    Ok(())
}
fn accepted_name(raw: &[u8], directory: bool) -> Result<String> {
    if raw.is_empty() || raw.len() > MAX_PATH { return Err(ErrorCode::LimitExceeded); }
    let name = std::str::from_utf8(raw).map_err(|_| ErrorCode::InvalidArchive)?;
    if name.starts_with('/') || name.contains('\\') || name.chars().any(|c| c.is_control() || "<>:\"|?*".contains(c)) { return Err(ErrorCode::InvalidArchive); }
    let body = if directory { name.strip_suffix('/').ok_or(ErrorCode::InvalidArchive)? } else { name };
    if body.is_empty() || body.split('/').any(|p| p.is_empty() || p == "." || p == ".." || p.ends_with('.') || p.ends_with(' ')) { return Err(ErrorCode::InvalidArchive); }
    // Match the product's portable source-component contract for files AND dirs.
    for component in body.split('/') {
        let device = component.split('.').next().unwrap_or("").to_uppercase();
        if matches!(device.as_str(), "CON" | "PRN" | "AUX" | "NUL" | "CONIN$" | "CONOUT$") {
            return Err(ErrorCode::InvalidArchive);
        }
        if let Some(suffix) = device.strip_prefix("COM").or_else(|| device.strip_prefix("LPT")) {
            let mut chars = suffix.chars();
            if matches!(chars.next(), Some('1'..='9' | '¹' | '²' | '³')) && chars.next().is_none() {
                return Err(ErrorCode::InvalidArchive);
            }
        }
    }
    Ok(name.to_owned())
}
fn alias_key(name: &str) -> String { name.nfd().default_case_fold().nfc().collect() }

// This is deliberately a narrow layout/budget preflight, not an alternate general ZIP parser.
// The maintained zip crate still parses the archive and decodes/checks every accepted member.
fn preflight(bytes: &[u8], deadline: Instant) -> Result<Vec<Member>> {
    if bytes.len() > MAX_ARCHIVE { return Err(ErrorCode::LimitExceeded); }
    if bytes.len() < 22 { return Err(ErrorCode::InvalidArchive); }
    // Pin the parser and this preflight to the same unique terminal record.
    // zip supports fallback EOCD scanning, which must not choose unchecked counts.
    let eocd = bytes.len() - 22;
    if u32at(bytes, eocd)? != 0x06054b50 || u16at(bytes, eocd + 20)? != 0 {
        return Err(ErrorCode::UnsupportedArchive);
    }
    if bytes[..eocd].windows(4).any(|w| w == b"PK\x05\x06") {
        return Err(ErrorCode::UnsupportedArchive);
    }
    let count = u16at(bytes, eocd + 10)? as usize;
    if count == 65535 || u32at(bytes, eocd + 12)? == u32::MAX || u32at(bytes, eocd + 16)? == u32::MAX { return Err(ErrorCode::UnsupportedArchive); }
    if u16at(bytes, eocd + 4)? != 0 || u16at(bytes, eocd + 6)? != 0 || u16at(bytes, eocd + 8)? as usize != count { return Err(ErrorCode::UnsupportedArchive); }
    if count > MAX_ENTRIES { return Err(ErrorCode::LimitExceeded); }
    let central_start = u32at(bytes, eocd + 16)? as usize;
    let central_size = u32at(bytes, eocd + 12)? as usize;
    if central_start.checked_add(central_size) != Some(eocd) { return Err(ErrorCode::InvalidArchive); }
    // Count and every record length are checked before asking zip to allocate metadata.
    let mut p = central_start;
    for _ in 0..count {
        check_deadline(deadline)?;
        if u32at(bytes, p)? != 0x02014b50 { return Err(ErrorCode::InvalidArchive); }
        let n = u16at(bytes, p + 28)? as usize;
        if n == 0 || n > MAX_PATH { return Err(ErrorCode::LimitExceeded); }
        p = p.checked_add(46 + n + u16at(bytes, p + 30)? as usize + u16at(bytes, p + 32)? as usize).ok_or(ErrorCode::InvalidArchive)?;
        if p > eocd { return Err(ErrorCode::InvalidArchive); }
    }
    if p != eocd { return Err(ErrorCode::InvalidArchive); }
    let mut members = Vec::with_capacity(count);
    let mut total = 0usize;
    p = central_start;
    for _ in 0..count {
        check_deadline(deadline)?;
        let flags = u16at(bytes, p + 8)?;
        let method = u16at(bytes, p + 10)?;
        if flags & !0x080e != 0 || (method == 0 && flags & 6 != 0) || !matches!(method, 0 | 8) || u16at(bytes, p + 6)? > 20 || u16at(bytes, p + 34)? != 0 { return Err(ErrorCode::UnsupportedArchive); }
        let compressed = u32at(bytes, p + 20)? as usize;
        let size = u32at(bytes, p + 24)? as usize;
        let local = u32at(bytes, p + 42)? as usize;
        if [compressed, size, local].contains(&(u32::MAX as usize)) { return Err(ErrorCode::UnsupportedArchive); }
        if size > MAX_FILE || compressed > MAX_ARCHIVE { return Err(ErrorCode::LimitExceeded); }
        total = total.checked_add(size).ok_or(ErrorCode::LimitExceeded)?;
        if total > MAX_TOTAL { return Err(ErrorCode::LimitExceeded); }
        let n = u16at(bytes, p + 28)? as usize;
        let extra = u16at(bytes, p + 30)? as usize;
        let comment = u16at(bytes, p + 32)? as usize;
        let raw = &bytes[p + 46..p + 46 + n];
        let directory = raw.ends_with(b"/");
        let path = accepted_name(raw, directory)?;
        let mode = u32at(bytes, p + 38)? >> 16;
        let kind = mode & 0o170000;
        if kind != 0 && kind != if directory { 0o040000 } else { 0o100000 } { return Err(ErrorCode::UnsupportedArchive); }
        if u32at(bytes, p + 38)? & 0x10 != 0 && !directory { return Err(ErrorCode::InvalidArchive); }
        if directory && (size != 0 || compressed != 0 || method != 0) { return Err(ErrorCode::InvalidArchive); }
        extra_fields(&bytes[p + 46 + n..p + 46 + n + extra])?;
        if u32at(bytes, local)? != 0x04034b50 || local >= central_start { return Err(ErrorCode::InvalidArchive); }
        if u16at(bytes, local + 4)? != u16at(bytes, p + 6)? || u16at(bytes, local + 6)? != flags || u16at(bytes, local + 8)? != method || bytes.get(local+10..local+14) != bytes.get(p+12..p+16) { return Err(ErrorCode::InvalidArchive); }
        let local_n = u16at(bytes, local + 26)? as usize;
        let local_extra = u16at(bytes, local + 28)? as usize;
        let data = local.checked_add(30 + local_n + local_extra).ok_or(ErrorCode::InvalidArchive)?;
        let data_end = data.checked_add(compressed).ok_or(ErrorCode::InvalidArchive)?;
        if data_end > central_start || bytes.get(local + 30..local + 30 + local_n) != Some(raw) { return Err(ErrorCode::InvalidArchive); }
        extra_fields(bytes.get(local + 30 + local_n..data).ok_or(ErrorCode::InvalidArchive)?)?;
        let crc = u32at(bytes, p + 16)?;
        for (lp, expected) in [(local+14, crc), (local+18, compressed as u32), (local+22, size as u32)] {
            let actual = u32at(bytes, lp)?;
            if actual != expected && !(flags & 8 != 0 && actual == 0) { return Err(ErrorCode::InvalidArchive); }
        }
        let mut end = data_end;
        if flags & 8 != 0 {
            // Both ZIP32 descriptor layouts are supported; ZIP64 descriptors are not.
            let matches = |at| u32at(bytes, at).ok() == Some(crc)
                && u32at(bytes, at+4).ok() == Some(compressed as u32)
                && u32at(bytes, at+8).ok() == Some(size as u32);
            if matches(end) { end += 12; }
            else if u32at(bytes, end)? == 0x08074b50 && matches(end + 4) { end += 16; }
            else { return Err(ErrorCode::InvalidArchive); }
        }
        if end > central_start { return Err(ErrorCode::InvalidArchive); }
        members.push(Member { path, directory, method, crc, compressed, size, local, central: p, data, end });
        p += 46 + n + extra + comment;
    }
    // Sort one canonical key per member: linear path storage, rather than allocating
    // every implicit prefix (which can be quadratic for deeply nested attacker paths).
    let mut aliases: Vec<_> = members.iter().enumerate()
        .map(|(i,m)| (alias_key(m.path.trim_end_matches('/')), i)).collect();
    // Component ordering keeps an explicit parent adjacent to its descendants;
    // raw string ordering would let punctuation siblings such as a! hide a/b.
    aliases.sort_unstable_by(|a,b| a.0.split('/').cmp(b.0.split('/')));
    for pair in aliases.windows(2) {
        let (left_key, left_index) = &pair[0];
        let (right_key, right_index) = &pair[1];
        if left_key == right_key { return Err(ErrorCode::InvalidArchive); }
        let left = &members[*left_index];
        let right = &members[*right_index];
        if !left.directory && right_key.starts_with(left_key)
            && right_key.as_bytes().get(left_key.len()) == Some(&b'/') {
            return Err(ErrorCode::InvalidArchive);
        }
        // Adjacent sorted keys witness every shared implicit directory. Reject
        // A/x with a/y and canonically equivalent spellings in any path component.
        for ((lk, rk), (lp, rp)) in left_key.split('/').zip(right_key.split('/'))
            .zip(left.path.trim_end_matches('/').split('/').zip(right.path.trim_end_matches('/').split('/'))) {
            if lk != rk { break; }
            if lp != rp { return Err(ErrorCode::InvalidArchive); }
        }
    }
    let mut ranges: Vec<_> = members.iter().map(|m| (m.local, m.end)).collect();
    ranges.sort_unstable();
    let mut end = 0;
    for (start, next) in ranges {
        // Reject overlap, unreferenced local entries, prefixes and inter-record gaps.
        if start != end || next <= start { return Err(ErrorCode::InvalidArchive); }
        end = next;
    }
    if end != central_start { return Err(ErrorCode::InvalidArchive); }
    Ok(members)
}
fn strict_deflate(compressed: &[u8], expected_size: usize, deadline: Instant) -> Result<()> {
    // zip's Read adapter validates CRC/decoded length but can accept EOF without an
    // explicit Deflate StreamEnd. Independently require one complete raw stream
    // consuming the entire declared compressed range; never retain duplicate output.
    let mut decoder = flate2::Decompress::new(false);
    let mut scratch = [0u8; 65536];
    loop {
        check_deadline(deadline)?;
        let before_in = decoder.total_in();
        let before_out = decoder.total_out();
        let status = decoder.decompress(&compressed[before_in as usize..], &mut scratch, flate2::FlushDecompress::None)
            .map_err(|_| ErrorCode::InvalidArchive)?;
        if decoder.total_out() > expected_size as u64 { return Err(ErrorCode::InvalidArchive); }
        if status == flate2::Status::StreamEnd {
            return if decoder.total_in() == compressed.len() as u64 && decoder.total_out() == expected_size as u64 {
                Ok(())
            } else { Err(ErrorCode::InvalidArchive) };
        }
        if decoder.total_in() == before_in && decoder.total_out() == before_out { return Err(ErrorCode::InvalidArchive); }
    }
}
fn import_bytes(bytes: &[u8], deadline: Instant) -> Result<(Vec<Entry>, usize, usize)> {
    let members = preflight(bytes, deadline)?;
    let mut archive = zip::ZipArchive::with_config(
        zip::read::Config { archive_offset: zip::read::ArchiveOffset::Known(0) },
        Cursor::new(bytes),
    ).map_err(|_| ErrorCode::InvalidArchive)?;
    if archive.len() != members.len() { return Err(ErrorCode::InvalidArchive); }
    let mut entries = Vec::new();
    let mut total = 0usize;
    for (i, m) in members.iter().enumerate() {
        check_deadline(deadline)?;
        if m.method == 8 {
            strict_deflate(&bytes[m.data..m.data + m.compressed], m.size, deadline)?;
        } else if m.compressed != m.size {
            return Err(ErrorCode::InvalidArchive);
        }
        let mut entry = archive.by_index(i).map_err(|_| ErrorCode::InvalidArchive)?;
        if entry.name_raw() != m.path.as_bytes() || entry.name() != m.path || entry.header_start() != m.local as u64
            || entry.central_header_start() != m.central as u64 || entry.data_start() != m.data as u64
            || entry.size() != m.size as u64 || entry.compressed_size() != m.compressed as u64
            || entry.crc32() != m.crc || entry.encrypted() || entry.is_dir() != m.directory
            || !matches!((entry.compression(), m.method), (zip::CompressionMethod::Stored, 0) | (zip::CompressionMethod::Deflated, 8)) {
            return Err(ErrorCode::InvalidArchive);
        }
        let mut decoded = Vec::with_capacity(m.size);
        let mut scratch = [0u8; 65536];
        loop {
            check_deadline(deadline)?;
            let n = entry.read(&mut scratch).map_err(|_| ErrorCode::InvalidArchive)?;
            if n == 0 { break; }
            if decoded.len().checked_add(n).ok_or(ErrorCode::LimitExceeded)? > m.size { return Err(ErrorCode::InvalidArchive); }
            total = total.checked_add(n).ok_or(ErrorCode::LimitExceeded)?;
            if total > MAX_TOTAL { return Err(ErrorCode::LimitExceeded); }
            decoded.extend_from_slice(&scratch[..n]);
        }
        if decoded.len() != m.size { return Err(ErrorCode::InvalidArchive); }
        if !m.directory {
            let info = EntryInfo { entry_id: entries.len(), path: m.path.clone(), size_bytes: decoded.len(), raw_sha256: sha256(&decoded) };
            entries.push(Entry { info, bytes: decoded.into_boxed_slice() });
        }
    }
    Ok((entries, members.len(), total))
}

#[cfg(test)]
mod tests;
