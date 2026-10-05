//! A single-process, single-import Linux IPC owner. No network or subprocess API is used.
#[cfg(target_os = "linux")]
mod linux {
    use base64::Engine;
    use rentgen_input_core::{ErrorCode, Request, Result, Session, MAX_FRAME};
    use serde_json::{json, Value};
    use std::io::{Read, Write};
    use std::path::Path;
    use std::time::{Duration, Instant};

    fn setup(parent: u32) -> Result<Instant> {
        use rustix::process::{getppid, set_parent_process_death_signal, set_dumpable_behavior, DumpableBehavior};
        // Establish ownership before emitting hello; checking after prctl closes the parent-exit race.
        set_parent_process_death_signal(Some(rustix::process::Signal::KILL)).map_err(|_| ErrorCode::InternalError)?;
        if parent <= 1 || getppid().map(|p| p.as_raw_pid() as u32) != Some(parent) { return Err(ErrorCode::InvalidState); }
        let end = Instant::now() + Duration::from_secs(60);
        // SAFETY: scalar-only close_range syscall. Inherited descriptors are not used by Rust
        // objects and this program owns the whole single-threaded process. Linux >=5.9 required.
        if unsafe { libc::syscall(libc::SYS_close_range, 3u32, u32::MAX, 0u32) } != 0 { return Err(ErrorCode::InternalError); }
        set_dumpable_behavior(DumpableBehavior::NotDumpable).map_err(|_| ErrorCode::InternalError)?;
        for (resource, limit) in [(libc::RLIMIT_AS, 128 * 1024 * 1024), (libc::RLIMIT_CORE, 0)] {
            let r = libc::rlimit { rlim_cur: limit, rlim_max: limit };
            // SAFETY: valid initialized rlimit pointer; only reducing this process's limits.
            if unsafe { libc::setrlimit(resource, &r) } != 0 { return Err(ErrorCode::InternalError); }
        }
        // Ensure an inherited blocked/ignored SIGALRM cannot defeat the wall deadline.
        // SAFETY: all pointers refer to initialized local signal-set storage.
        unsafe {
            if libc::signal(libc::SIGALRM, libc::SIG_DFL) == libc::SIG_ERR { return Err(ErrorCode::InternalError); }
            let mut set: libc::sigset_t = std::mem::zeroed();
            if libc::sigemptyset(&mut set) != 0 || libc::sigaddset(&mut set, libc::SIGALRM) != 0
                || libc::sigprocmask(libc::SIG_UNBLOCK, &set, std::ptr::null_mut()) != 0 { return Err(ErrorCode::InternalError); }
        }
        arm_deadline(end)?;
        Ok(end)
    }
    fn arm_deadline(end: Instant) -> Result<()> {
        let left = end.checked_duration_since(Instant::now()).ok_or(ErrorCode::DeadlineExceeded)?;
        let micros = left.as_micros().max(1);
        let timer = libc::itimerval {
            it_interval: libc::timeval { tv_sec: 0, tv_usec: 0 },
            it_value: libc::timeval { tv_sec: (micros / 1_000_000) as _, tv_usec: (micros % 1_000_000) as _ },
        };
        // SAFETY: scalar syscall plus a valid initialized timer pointer, no retained pointers.
        if unsafe { libc::syscall(libc::SYS_setitimer, libc::ITIMER_REAL, &timer, std::ptr::null_mut::<libc::itimerval>()) } != 0 { return Err(ErrorCode::InternalError); }
        Ok(())
    }
    fn send(value: Value) -> Result<()> {
        let bytes = serde_json::to_vec(&value).map_err(|_| ErrorCode::InternalError)?;
        if bytes.len() > MAX_FRAME { return Err(ErrorCode::LimitExceeded); }
        let mut out = std::io::stdout().lock();
        out.write_all(&(bytes.len() as u32).to_le_bytes()).and_then(|_| out.write_all(&bytes)).and_then(|_| out.flush()).map_err(|_| ErrorCode::IoError)
    }
    fn error(seq: u64, code: ErrorCode) -> Result<()> {
        send(json!({"protocol":1,"seq":seq,"error":{"code":code,"message":code.message()}}))
    }
    fn read_frame(input: &mut impl Read) -> Result<Option<Vec<u8>>> {
        let mut header = [0u8; 4];
        let mut got = 0;
        while got < 4 {
            let n = input.read(&mut header[got..]).map_err(|_| ErrorCode::IoError)?;
            if n == 0 { return if got == 0 { Ok(None) } else { Err(ErrorCode::InvalidRequest) }; }
            got += n;
        }
        let n = u32::from_le_bytes(header) as usize;
        // The peer cannot request allocation before this fixed framing bound is checked.
        if n == 0 || n > MAX_FRAME { return Err(ErrorCode::LimitExceeded); }
        let mut bytes = vec![0u8; n];
        input.read_exact(&mut bytes).map_err(|_| ErrorCode::InvalidRequest)?;
        Ok(Some(bytes))
    }
    pub fn run() -> Result<()> {
        let args: Vec<_> = std::env::args().collect();
        if args.len() != 3 || args[1] != "--parent-pid" { return Err(ErrorCode::InvalidRequest); }
        let parent = args[2].parse().map_err(|_| ErrorCode::InvalidRequest)?;
        let deadline = setup(parent)?;
        send(json!({"protocol":1,"kind":"hello","implementation":"rentgen-input-core","contract":"submitted-zip-v1"}))?;
        let mut input = std::io::stdin().lock();
        let mut next_seq = 1u64;
        let mut session: Option<Session> = None;
        loop {
            let bytes = match read_frame(&mut input) {
                Ok(Some(bytes)) => bytes,
                // EOF closes and drops any accepted input, but is not a successful close acknowledgment.
                Ok(None) => return Err(ErrorCode::IoError),
                Err(code) => { error(0, code)?; return Err(code); }
            };
            let request: Request = match serde_json::from_slice(&bytes) {
                Ok(r) => r,
                Err(_) => { error(0, ErrorCode::InvalidRequest)?; return Err(ErrorCode::InvalidRequest); }
            };
            let (protocol, seq) = request.protocol_seq();
            if protocol != 1 { error(seq, ErrorCode::InvalidRequest)?; return Err(ErrorCode::InvalidRequest); }
            if seq != next_seq { error(seq, ErrorCode::InvalidSequence)?; return Err(ErrorCode::InvalidSequence); }
            next_seq = next_seq.checked_add(1).ok_or(ErrorCode::InvalidSequence)?;
            let result = match request {
                Request::OpenImport { path, expected_sha256, .. } => {
                    if session.is_some() { error(seq, ErrorCode::InvalidState)?; return Err(ErrorCode::InvalidState); }
                    arm_deadline(deadline.min(Instant::now() + Duration::from_secs(10)))?;
                    match Session::open(Path::new(&path), &expected_sha256) {
                        Ok(opened) => {
                            arm_deadline(deadline)?;
                            let result = serde_json::to_value(opened.info()).map_err(|_| ErrorCode::InternalError)?;
                            session = Some(opened);
                            Ok(result)
                        }
                        Err(code) => { error(seq, code)?; return Err(code); }
                    }
                }
                Request::Entries { offset, limit, .. } => match &session {
                    Some(s) => s.entries(offset, limit).map(|(entries, next_offset)| json!({"entries":entries,"next_offset":next_offset})),
                    None => Err(ErrorCode::InvalidState),
                },
                Request::ReadEntry { entry_id, offset, limit, .. } => match &session {
                    Some(s) => s.read_entry(entry_id, offset, limit).map(|(info, bytes, next_offset)| json!({
                        "entry_id":entry_id,"offset":offset,"total_bytes":info.size_bytes,"raw_sha256":info.raw_sha256,
                        "data_base64":base64::engine::general_purpose::STANDARD.encode(bytes),"next_offset":next_offset
                    })),
                    None => Err(ErrorCode::InvalidState),
                },
                Request::Close { .. } => {
                    drop(session.take());
                    send(json!({"protocol":1,"seq":seq,"result":{"closed":true}}))?;
                    return Ok(());
                }
            };
            match result {
                Ok(result) => send(json!({"protocol":1,"seq":seq,"result":result}))?,
                Err(code) => error(seq, code)?,
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn frame_limits_precede_body_read() {
            assert_eq!(read_frame(&mut &u32::MAX.to_le_bytes()[..]), Err(ErrorCode::LimitExceeded));
            assert_eq!(read_frame(&mut &0u32.to_le_bytes()[..]), Err(ErrorCode::LimitExceeded));
            assert_eq!(read_frame(&mut &b"\x01\x00"[..]), Err(ErrorCode::InvalidRequest));
            assert_eq!(read_frame(&mut &b"\x02\x00\x00\x00x"[..]), Err(ErrorCode::InvalidRequest));
            assert_eq!(read_frame(&mut &b""[..]), Ok(None));
        }
    }
}
fn main() {
    // Never format source bytes, paths, arbitrary OS errors, or panics to stderr.
    std::panic::set_hook(Box::new(|_| {}));
    #[cfg(target_os = "linux")]
    std::process::exit(if linux::run().is_ok() { 0 } else { 1 });
    #[cfg(not(target_os = "linux"))]
    std::process::exit(1);
}
