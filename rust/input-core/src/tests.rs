use super::*;
use std::io::Write;
use std::sync::atomic::{AtomicU64, Ordering};

fn crc32(data: &[u8]) -> u32 {
    let mut crc = !0u32;
    for &b in data {
        crc ^= b as u32;
        for _ in 0..8 { crc = (crc >> 1) ^ (0xedb88320u32 & (0u32.wrapping_sub(crc & 1))); }
    }
    !crc
}
fn put16(b: &mut [u8], p: usize, n: u16) { b[p..p+2].copy_from_slice(&n.to_le_bytes()); }
fn put32(b: &mut [u8], p: usize, n: u32) { b[p..p+4].copy_from_slice(&n.to_le_bytes()); }
fn fixture(files: &[(&str, &[u8])], deflate: bool, descriptor: bool) -> Vec<u8> {
    let mut out = Vec::new();
    let mut central = Vec::new();
    for (name, data) in files {
        let directory = name.ends_with('/');
        let compressed = if deflate && !directory {
            let mut encoder = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
            encoder.write_all(data).unwrap(); encoder.finish().unwrap()
        } else { data.to_vec() };
        let method = if deflate && !directory { 8 } else { 0 };
        let flags = 0x800 | if descriptor { 8 } else { 0 };
        let local = out.len();
        let mut h = vec![0u8; 30];
        put32(&mut h, 0, 0x04034b50); put16(&mut h, 4, 20); put16(&mut h, 6, flags); put16(&mut h, 8, method);
        if !descriptor { put32(&mut h, 14, crc32(data)); put32(&mut h, 18, compressed.len() as u32); put32(&mut h, 22, data.len() as u32); }
        put16(&mut h, 26, name.len() as u16);
        out.extend(h); out.extend(name.as_bytes()); out.extend(&compressed);
        if descriptor { out.extend(0x08074b50u32.to_le_bytes()); out.extend(crc32(data).to_le_bytes()); out.extend((compressed.len() as u32).to_le_bytes()); out.extend((data.len() as u32).to_le_bytes()); }
        let mut c = vec![0u8; 46];
        put32(&mut c, 0, 0x02014b50); put16(&mut c, 4, 0x314); put16(&mut c, 6, 20); put16(&mut c, 8, flags); put16(&mut c, 10, method);
        put32(&mut c, 16, crc32(data)); put32(&mut c, 20, compressed.len() as u32); put32(&mut c, 24, data.len() as u32); put16(&mut c, 28, name.len() as u16);
        put32(&mut c, 38, if directory { (0o040755 << 16) | 0x10 } else { 0o100644 << 16 }); put32(&mut c, 42, local as u32);
        central.extend(c); central.extend(name.as_bytes());
    }
    let start = out.len(); let size = central.len(); out.extend(central);
    let mut e = vec![0u8; 22]; put32(&mut e, 0, 0x06054b50); put16(&mut e, 8, files.len() as u16); put16(&mut e, 10, files.len() as u16); put32(&mut e, 12, size as u32); put32(&mut e, 16, start as u32); out.extend(e); out
}
fn central(b: &[u8]) -> usize { u32at(b, b.len()-6).unwrap() as usize }
fn imported(b: &[u8]) -> Result<(Vec<Entry>, usize, usize)> { import_bytes(b, Instant::now() + Duration::from_secs(2)) }
fn rejected(b: &[u8]) { assert!(imported(b).is_err()); }

#[test]
fn stored_deflate_and_descriptors_preserve_archive_root() {
    for deflate in [false, true] { for descriptor in [false, true] {
        let b = fixture(&[("Export/", b""), ("Export/Configuration.xml", b"<Metadata/>"), ("Export/Module.bsl", "Процедура".as_bytes())], deflate, descriptor);
        let (entries, count, total) = imported(&b).unwrap();
        assert_eq!(count, 3); assert_eq!(entries.len(), 2); assert_eq!(entries[0].info.path, "Export/Configuration.xml");
        assert_eq!(entries[0].bytes.as_ref(), b"<Metadata/>"); assert_eq!(total, b"<Metadata/>".len() + "Процедура".len());
    }}
}
#[test]
fn rejects_bad_paths_and_unicode_aliases() {
    for name in ["../x", "/x", "a/../x", "a//x", "a\\x", "C:x", "a./x", "a /x", "./x", "a\nx", ""] { rejected(&fixture(&[(name, b"x")], false, false)); }
    for (a,b) in [("A.xml","a.xml"), ("é.xml","e\u{301}.xml"), ("ß.xml","ss.xml"), ("A/x","a/y"), ("a","a/b"), ("a","a/"), ("x","x")] {
        rejected(&fixture(&[(a,b""),(b,b"")], false, false));
    }
}
#[test]
fn rejects_special_and_encrypted_members() {
    for kind in [0o120777, 0o010600, 0o020600, 0o060600, 0o140600] {
        let mut b = fixture(&[("x",b"abc")], false, false); let c=central(&b); put32(&mut b,c+38,kind<<16); rejected(&b);
    }
    for flags in [1, 0x40, 0x2000, 0x10] {
        let mut b=fixture(&[("x",b"abc")], false, false); let c=central(&b); put16(&mut b,6,flags); put16(&mut b,c+8,flags); rejected(&b);
    }
}
#[test]
fn rejects_zip64_multidisk_and_unknown_compression() {
    for offset in [20,24,42] { let mut b=fixture(&[("x",b"abc")], false, false); let c=central(&b); put32(&mut b,c+offset,u32::MAX); rejected(&b); }
    for offset in [4,6] { let mut b=fixture(&[("x",b"abc")], false, false); let e=b.len()-22; put16(&mut b,e+offset,1); rejected(&b); }
    let mut b=fixture(&[("x",b"abc")], false, false); let c=central(&b); put16(&mut b,8,12); put16(&mut b,c+10,12); rejected(&b);
}
#[test]
fn rejects_local_central_disagreements_and_crc_failure() {
    for offset in [4,6,8,10,14,18,22,26,30] { let mut b=fixture(&[("x",b"abc")], false, false); b[offset]^=1; rejected(&b); }
    let mut b=fixture(&[("x",b"abc")], false, false); b[31]^=1; rejected(&b);
    let mut b=fixture(&[("x",b"abc")], true, false); b[31]^=0x80; rejected(&b);
}
#[test]
fn rejects_overlap_missing_records_and_nonzip_prefix() {
    let mut b=fixture(&[("x",b"abc"),("y",b"def")], false, false); let c=central(&b); put32(&mut b,c+47+42,0); rejected(&b);
    let mut b=fixture(&[("x",b"abc")], false, false); let e=b.len()-22; put16(&mut b,e+8,2); put16(&mut b,e+10,2); rejected(&b);
    let mut b=fixture(&[("x",b"abc")], false, false); b.insert(0,0); rejected(&b);
    let mut b=fixture(&[("x",b"abc")], false, false); b.push(0); rejected(&b);
}
#[test]
fn rejects_declared_size_and_entry_budget_before_decode() {
    let mut b=fixture(&[("x",b"abc")], false, false); let c=central(&b); put32(&mut b,c+24,(MAX_FILE+1) as u32); rejected(&b);
    let mut b=fixture(&[("x",b"abc")], false, false); let e=b.len()-22; put16(&mut b,e+8,4097); put16(&mut b,e+10,4097); assert_eq!(preflight(&b,Instant::now()+Duration::from_secs(1)).unwrap_err(),ErrorCode::LimitExceeded);
    let b=vec![0;MAX_ARCHIVE+1]; assert_eq!(preflight(&b,Instant::now()+Duration::from_secs(1)).unwrap_err(),ErrorCode::LimitExceeded);
}
#[test]
fn rejects_false_actual_size_and_zip_bomb() {
    for deflate in [false,true] {
        let mut b=fixture(&[("x",b"abcdef")], deflate, false); let c=central(&b); put32(&mut b,22,2); put32(&mut b,c+24,2); rejected(&b);
    }
    let data=vec![b'x';MAX_FILE+1]; let mut b=fixture(&[("bomb",&data)], true, false); let c=central(&b); put32(&mut b,22,1); put32(&mut b,c+24,1); rejected(&b);
}
#[test]
fn strict_request_fields_types_duplicates_and_trailing_data() {
    for json in [
        r#"{"protocol":1,"seq":1,"op":"close","extra":1}"#,
        r#"{"protocol":1,"protocol":1,"seq":1,"op":"close"}"#,
        r#"{"protocol":1,"seq":1,"seq":1,"op":"close"}"#,
        r#"{"protocol":1,"seq":1,"op":"close","op":"close"}"#,
        r#"{"protocol":1,"seq":1.0,"op":"close"}"#,
        r#"{"protocol":1,"seq":-1,"op":"close"}"#,
        r#"{"protocol":1,"seq":true,"op":"close"}"#,
        r#"{"protocol":1,"seq":1,"op":"close"} {}"#,
        r#"{"protocol":1,"seq":1,"op":"entries","offset":0,"limit":32,"path":"x"}"#,
        r#"{"protocol":1,"seq":1,"op":"open_import","path":"/a","path":"/b","expected_sha256":"x"}"#,
    ] { assert!(serde_json::from_str::<Request>(json).is_err(),"accepted {json}"); }
    assert!(serde_json::from_str::<Request>(r#"{"protocol":1,"seq":1,"op":"close"}"#).is_ok());
}
#[test]
fn deadline_is_checked_during_preflight() {
    assert_eq!(preflight(&fixture(&[("x",b"a")],false,false),Instant::now()-Duration::from_secs(1)).unwrap_err(), ErrorCode::DeadlineExceeded);
}

#[cfg(target_os="linux")]
struct Temp(std::path::PathBuf);
#[cfg(target_os="linux")]
impl Temp {
    fn new() -> Self { static N:AtomicU64=AtomicU64::new(0); let p=std::env::temp_dir().join(format!("rentgen-rust-test-{}-{}",std::process::id(),N.fetch_add(1,Ordering::Relaxed))); std::fs::create_dir(&p).unwrap(); Self(p) }
    fn zip(&self) -> (std::path::PathBuf,Vec<u8>) { let b=fixture(&[("Configuration.xml",b"<root/>")],false,false); let p=self.0.join("input.zip"); std::fs::write(&p,&b).unwrap(); (p,b) }
}
#[cfg(target_os="linux")]
impl Drop for Temp { fn drop(&mut self) { let _=std::fs::remove_dir_all(&self.0); } }
#[cfg(target_os="linux")]
#[test]
fn retained_bytes_survive_source_replacement_and_mutation() {
    let t=Temp::new(); let(p,b)=t.zip(); let s=Session::open(&p,&sha256(&b)).unwrap();
    std::fs::write(&p,b"changed").unwrap(); std::fs::rename(&p,t.0.join("old")).unwrap(); std::fs::write(&p,b"replacement").unwrap();
    assert_eq!(s.read_entry(0,0,MAX_CHUNK).unwrap().1,b"<root/>"); assert!(s.read_entry(0,0,MAX_CHUNK+1).is_err()); assert!(s.entries(0,33).is_err());
}
#[cfg(target_os="linux")]
#[test]
fn rejects_leaf_ancestor_symlink_hardlink_and_fifo_without_blocking() {
    use std::os::unix::fs::symlink;
    let t=Temp::new(); let(p,b)=t.zip(); let hash=sha256(&b);
    let link=t.0.join("link.zip"); symlink(&p,&link).unwrap(); assert!(Session::open(&link,&hash).is_err());
    let dir=t.0.join("linkdir"); symlink(&t.0,&dir).unwrap(); assert!(Session::open(&dir.join("input.zip"),&hash).is_err());
    std::fs::hard_link(&p,t.0.join("hard.zip")).unwrap(); assert!(Session::open(&p,&hash).is_err());
    let fifo=t.0.join("fifo"); rustix::fs::mknodat(rustix::fs::CWD,&fifo,rustix::fs::FileType::Fifo,rustix::fs::Mode::RUSR|rustix::fs::Mode::WUSR,0).unwrap();
    assert!(Session::open(&fifo,&hash).is_err());
}
#[cfg(target_os="linux")]
#[test]
fn refuses_hash_mismatch_and_noncanonical_locator() {
    let t=Temp::new(); let(p,b)=t.zip(); assert!(matches!(Session::open(&p,&"0".repeat(64)),Err(ErrorCode::HashMismatch)));
    assert!(Session::open(Path::new("input.zip"),&sha256(&b)).is_err());
    let bad=p.parent().unwrap().join(".").join("input.zip"); assert!(Session::open(&bad,&sha256(&b)).is_err());
}

#[test]
fn strict_deflate_requires_final_complete_stream_and_exact_compressed_extent() {
    let deadline=Instant::now()+Duration::from_secs(1);
    assert!(strict_deflate(&[0x4b,0x4c,0x4a,0x06,0x00],3,deadline).is_ok());
    for bytes in [&[0x4b,0x4c,0x4a,0x06][..], &[0x4a,0x4c,0x4a,0x06,0x00][..],
        &[0x4b,0x4c,0x4a,0x06,0x00,0xff][..]] {
        assert_eq!(strict_deflate(bytes,3,deadline),Err(ErrorCode::InvalidArchive));
    }
    for bytes in [&[][..], &[0][..]] { assert_eq!(strict_deflate(bytes,0,deadline),Err(ErrorCode::InvalidArchive)); }
    assert!(strict_deflate(&[3,0],0,deadline).is_ok());
}
#[test]
fn deeply_nested_names_have_linear_alias_storage_and_remain_valid() {
    let names:Vec<_>=(0..256).map(|i|format!("{i:03}/{}x","a/".repeat(490))).collect();
    let files:Vec<_>=names.iter().map(|n|(n.as_str(),&b""[..])).collect();
    let (entries,count,total)=imported(&fixture(&files,false,false)).unwrap();
    assert_eq!((entries.len(),count,total),(256,256,0));
}

#[test]
fn punctuation_siblings_cannot_hide_file_or_directory_aliases() {
    for middle in ["a!","a.b","a-b"] {
        rejected(&fixture(&[("a",b""),(middle,b""),("a/b",b"")],false,false));
        rejected(&fixture(&[("A/",b""),(middle,b""),("a/b",b"")],false,false));
    }
}
#[test]
fn unsigned_descriptor_crc_may_equal_signature_magic() {
    let payload=[0xac,0x0a,0x7a,0xd5]; assert_eq!(crc32(&payload),0x08074b50);
    let mut b=fixture(&[("x",&payload)],false,true);
    let descriptor=31+payload.len(); b.drain(descriptor..descriptor+4);
    let e=b.len()-22; let start=u32at(&b,e+16).unwrap()-4; put32(&mut b,e+16,start);
    assert!(imported(&b).is_ok());
}

#[test]
fn rejects_archive_comment_and_embedded_or_fallback_eocd_before_zip_parser() {
    let mut b=fixture(&[("x",b"abc")],false,false); let e=b.len()-22; put16(&mut b,e+20,1); b.push(b'x');
    assert_eq!(preflight(&b,Instant::now()+Duration::from_secs(1)).unwrap_err(),ErrorCode::UnsupportedArchive);
    let b=fixture(&[("x",b"PK\x05\x06")],false,false);
    assert_eq!(preflight(&b,Instant::now()+Duration::from_secs(1)).unwrap_err(),ErrorCode::UnsupportedArchive);
    // An earlier malicious fallback footer with an unchecked large member count,
    // inside Stored source bytes, must never reach ZipArchive::get_metadata.
    let mut fake=vec![0u8;22]; put32(&mut fake,0,0x06054b50); put16(&mut fake,8,65534); put16(&mut fake,10,65534);
    let mut b=fixture(&[("x",&fake)],false,false); let c=central(&b); b[c+4]=0xff;
    assert_eq!(preflight(&b,Instant::now()+Duration::from_secs(1)).unwrap_err(),ErrorCode::UnsupportedArchive);
}

#[test]
fn portable_component_contract_applies_to_files_and_empty_directories() {
    for component in ["a<b","a>b","a\"b","a|b","a?b","a*b","CON","NUL.txt","aux","PrN",
        "CONIN$","conout$.log","COM1","com9.txt","LPT1","LPT9.x","COM¹","LPT².txt","lpt³"] {
        rejected(&fixture(&[(component,b"")],false,false));
        rejected(&fixture(&[(&format!("{component}/"),b"")],false,false));
        rejected(&fixture(&[(&format!("safe/{component}/x"),b"")],false,false));
    }
    for component in ["COM0","COM10","LPT0","LPT10","company","console"] {
        assert!(imported(&fixture(&[(component,b"")],false,false)).is_ok());
    }
}
