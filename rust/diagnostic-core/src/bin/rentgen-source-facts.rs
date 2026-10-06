//! Linux-only one-shot transport. Native ownership is isolated from the pure library.
#[cfg(target_os = "linux")]
mod linux {
    use rentgen_diagnostic_core::source_facts::{self, INPUT_LIMIT, OUTPUT_LIMIT};
    use std::io::{self, Read, Write};

    const HELLO: &[u8] = b"{\"protocol\":\"submitted_source_facts_v1\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\"}";
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    enum Error { InvalidEnvelope, InputLimit, IoError, InternalError }
    impl Error {
        fn bytes(self) -> &'static [u8] {
            match self {
                Self::InvalidEnvelope => b"{\"protocol\":\"submitted_source_facts_v1\",\"status\":\"error\",\"code\":\"invalid_envelope\"}",
                Self::InputLimit => b"{\"protocol\":\"submitted_source_facts_v1\",\"status\":\"error\",\"code\":\"input_limit\"}",
                Self::IoError => b"{\"protocol\":\"submitted_source_facts_v1\",\"status\":\"error\",\"code\":\"io_error\"}",
                Self::InternalError => b"{\"protocol\":\"submitted_source_facts_v1\",\"status\":\"error\",\"code\":\"internal_error\"}",
            }
        }
    }
    fn parent_argument(args: impl IntoIterator<Item = std::ffi::OsString>) -> Option<libc::pid_t> {
        let mut args = args.into_iter();
        args.next()?;
        if args.next()? != "--parent-pid" { return None; }
        let raw = args.next()?;
        if args.next().is_some() { return None; }
        let text = raw.to_str()?;
        if text.is_empty() || text.starts_with('0') || !text.bytes().all(|b| b.is_ascii_digit()) { return None; }
        let pid: libc::pid_t = text.parse().ok()?;
        (pid > 1).then_some(pid)
    }
    fn setup(parent: libc::pid_t) -> Result<(), Error> {
        // This executable never spawns threads. The main/ownership thread remains
        // alive until process exit. The host must likewise retain its launch thread.
        // SAFETY: fixed scalar prctl arguments; GET writes one initialized c_int.
        // Parent comparison AFTER setting and verifying closes the parent-exit race.
        unsafe {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL as libc::c_ulong,
                           0usize, 0usize, 0usize) != 0 { return Err(Error::InternalError); }
            let mut installed: libc::c_int = 0;
            if libc::prctl(libc::PR_GET_PDEATHSIG, &mut installed as *mut libc::c_int,
                           0usize, 0usize, 0usize) != 0
                || installed != libc::SIGKILL || libc::getppid() != parent {
                return Err(Error::InternalError);
            }
            if libc::prctl(libc::PR_SET_DUMPABLE, 0usize, 0usize, 0usize, 0usize) != 0
                || libc::prctl(libc::PR_GET_DUMPABLE, 0usize, 0usize, 0usize, 0usize) != 0 {
                return Err(Error::InternalError);
            }
        }
        // A small Rust process, with no Go virtual-address reservation. These are
        // resource caps, not sandbox/provenance guarantees. Never raise inherited caps.
        for (resource, cap) in [(libc::RLIMIT_CORE, 0),
            (libc::RLIMIT_AS, 128 * 1024 * 1024), (libc::RLIMIT_CPU, 5)] {
            // SAFETY: get/setrlimit receive valid initialized stack storage; no
            // pointers escape, and only this process's limits are reduced.
            unsafe {
                let mut previous = libc::rlimit { rlim_cur: 0, rlim_max: 0 };
                if libc::getrlimit(resource, &mut previous) != 0 { return Err(Error::InternalError); }
                let limit = previous.rlim_cur.min(previous.rlim_max).min(cap);
                let limits = libc::rlimit { rlim_cur: limit, rlim_max: limit };
                if libc::setrlimit(resource, &limits) != 0 { return Err(Error::InternalError); }
            }
        }
        // The one-shot wall watchdog covers hello, input/EOF, parsing and output,
        // including a pipe held open forever. Reset inherited ignored/blocked ALRM.
        // SAFETY: fixed signal/default handler and initialized stack signal set.
        unsafe {
            if libc::signal(libc::SIGALRM, libc::SIG_DFL) == libc::SIG_ERR { return Err(Error::InternalError); }
            let mut set: libc::sigset_t = std::mem::zeroed();
            if libc::sigemptyset(&mut set) != 0 || libc::sigaddset(&mut set, libc::SIGALRM) != 0
                || libc::sigprocmask(libc::SIG_UNBLOCK, &set, std::ptr::null_mut()) != 0 {
                return Err(Error::InternalError);
            }
            libc::alarm(5);
        }
        Ok(())
    }
    fn read_error(error: io::Error) -> Error {
        if error.kind() == io::ErrorKind::UnexpectedEof { Error::InvalidEnvelope }
        else { Error::IoError }
    }
    fn read_request(input: &mut impl Read) -> Result<Vec<u8>, Error> {
        let mut header = [0u8; 4];
        input.read_exact(&mut header).map_err(read_error)?;
        let len = u32::from_le_bytes(header) as usize;
        if len > INPUT_LIMIT { return Err(Error::InputLimit); }
        if len == 0 { return Err(Error::InvalidEnvelope); }
        let mut payload = vec![0u8; len];
        input.read_exact(&mut payload).map_err(read_error)?;
        let mut tail = [0u8; 1];
        loop {
            match input.read(&mut tail) {
                Ok(0) => return Ok(payload),
                Ok(_) => return Err(Error::InvalidEnvelope),
                Err(e) if e.kind() == io::ErrorKind::Interrupted => (),
                Err(_) => return Err(Error::IoError),
            }
        }
    }
    fn send(output: &mut impl Write, payload: &[u8]) -> Result<(), Error> {
        if payload.len() > OUTPUT_LIMIT { return Err(Error::InternalError); }
        output.write_all(&(payload.len() as u32).to_le_bytes())
            .and_then(|_| output.write_all(payload)).and_then(|_| output.flush())
            .map_err(|_| Error::IoError)
    }
    fn exchange() -> Result<Vec<u8>, Error> {
        let payload = read_request(&mut io::stdin().lock())?;
        let result = source_facts::evaluate(&payload).map_err(|error| match error {
            source_facts::Error::InvalidEnvelope => Error::InvalidEnvelope,
            source_facts::Error::InputLimit => Error::InputLimit,
        })?;
        let bytes = serde_json::to_vec(&result).map_err(|_| Error::InternalError)?;
        if bytes.len() > OUTPUT_LIMIT { return Err(Error::InternalError); }
        Ok(bytes)
    }
    pub fn run() -> bool {
        let Some(parent) = parent_argument(std::env::args_os()) else { return false; };
        if setup(parent).is_err() { return false; }
        if send(&mut io::stdout().lock(), HELLO).is_err() { return false; }
        let result = std::panic::catch_unwind(exchange).unwrap_or(Err(Error::InternalError));
        let success = result.is_ok();
        let bytes = match &result { Ok(bytes) => bytes.as_slice(), Err(error) => error.bytes() };
        // A partial write cannot be repaired by emitting a second response.
        send(&mut io::stdout().lock(), bytes).is_ok() && success
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn pid_argument_has_exact_unsigned_lexeme_and_shape() {
            for raw in ["", "0", "1", "-0", "-2", "+2", "02", " 2", "2 ", "2.0", "2e1", "2147483648"] {
                assert_eq!(parent_argument(["exe", "--parent-pid", raw].map(Into::into)), None);
            }
            assert_eq!(parent_argument(["exe", "--parent-pid", "2"].map(Into::into)), Some(2));
            assert_eq!(parent_argument(["exe", "--parent-pid", "2", "x"].map(Into::into)), None);
            assert_eq!(parent_argument(["exe", "--parent", "2"].map(Into::into)), None);
        }
        #[test]
        fn framing_checks_length_before_allocation_and_requires_exact_eof() {
            assert_eq!(read_request(&mut &u32::MAX.to_le_bytes()[..]), Err(Error::InputLimit));
            assert_eq!(read_request(&mut &0u32.to_le_bytes()[..]), Err(Error::InvalidEnvelope));
            for bytes in [&b""[..], &b"\x01\x00"[..], &b"\x02\x00\x00\x00x"[..],
                          &b"\x02\x00\x00\x00{}x"[..]] {
                assert_eq!(read_request(&mut &bytes[..]), Err(Error::InvalidEnvelope));
            }
            assert_eq!(read_request(&mut &b"\x02\x00\x00\x00{}"[..]), Ok(b"{}".to_vec()));
        }
    }
}
fn main() {
    // No panic, OS error, argv, path or input value reaches stderr.
    std::panic::set_hook(Box::new(|_| {}));
    #[cfg(target_os = "linux")]
    let success = std::panic::catch_unwind(linux::run).unwrap_or(false);
    #[cfg(not(target_os = "linux"))]
    let success = false;
    std::process::exit(if success { 0 } else { 2 });
}
