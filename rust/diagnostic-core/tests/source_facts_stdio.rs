//! Linux development checks for the separate executable, never source fixtures.
#![cfg(target_os = "linux")]
use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

const HELLO: &[u8] = b"{\"protocol\":\"submitted_source_facts_v1\",\"kind\":\"hello\",\"ownership\":\"linux_parent_death_v1\"}";
const ABSTENTION: &[u8] = br#"{"schema_version":2,"profile":"submitted_source_facts_v1","rule_set":"source_observations_v1","scope":{"case_id":1,"input_id":2,"selector_id":3,"caller_entry_id":4,"candidate_entry_id":5,"xml_entry_id":null},"observations":{"selector":{"state":"unavailable","reason":"selector_not_qualified"},"export":{"state":"unavailable","reason":"selector_unavailable"},"server":{"state":"unavailable","reason":"selector_unavailable"}},"receipts":{"selector":null,"export":null,"server":null},"receiver_binding":"unknown","runtime_relation":"unknown"}"#;
fn frame(input: &[u8]) -> Vec<u8> { [(input.len() as u32).to_le_bytes().as_slice(),input].concat() }
fn read_frame(input: &mut impl Read) -> Vec<u8> {
    let mut header = [0u8;4]; input.read_exact(&mut header).unwrap();
    let len = u32::from_le_bytes(header) as usize; assert!(len <= 65_536);
    let mut payload = vec![0;len]; input.read_exact(&mut payload).unwrap(); payload
}
fn start() -> Child {
    Command::new(env!("CARGO_BIN_EXE_rentgen-source-facts"))
        .args(["--parent-pid", &std::process::id().to_string()])
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap()
}
fn exchange(input: &[u8]) -> std::process::Output {
    let mut child = start();
    assert_eq!(read_frame(child.stdout.as_mut().unwrap()), HELLO);
    child.stdin.take().unwrap().write_all(input).unwrap();
    child.wait_with_output().unwrap()
}
fn error(output: std::process::Output, code: &str) {
    assert_eq!(output.status.code(), Some(2)); assert!(output.stderr.is_empty());
    let expected = format!("{{\"protocol\":\"submitted_source_facts_v1\",\"status\":\"error\",\"code\":\"{code}\"}}");
    assert_eq!(output.stdout, frame(expected.as_bytes()));
}
#[test]
fn hello_then_one_compact_success_frame_eof_and_zero_exit() {
    let output = exchange(&frame(ABSTENTION));
    assert!(output.status.success()); assert!(output.stderr.is_empty());
    let expected = serde_json::to_vec(&rentgen_diagnostic_core::source_facts::evaluate(ABSTENTION).unwrap()).unwrap();
    assert_eq!(output.stdout, frame(&expected)); assert!(!expected.ends_with(b"\n"));
}
#[test]
fn malformed_frames_errors_and_canaries_never_echo() {
    for input in [vec![], vec![1,0], vec![2,0,0,0,b'{'], frame(b"{}"), frame(b"{\"path\":\"CANARY_SECRET_SOURCE_PATH\"}"),
        [frame(ABSTENTION),vec![b'\n']].concat(), [frame(ABSTENTION),frame(ABSTENTION)].concat(), vec![0,0,0,0]] {
        error(exchange(&input), "invalid_envelope");
    }
    error(exchange(&65_537u32.to_le_bytes()), "input_limit");
    error(exchange(&u32::MAX.to_le_bytes()), "input_limit");
}
#[test]
fn setup_failure_is_silent_and_accepts_no_other_argv() {
    for args in [vec![], vec!["--parent-pid", "1"], vec!["--parent-pid", "0"],
        vec!["--parent-pid", "CANARY_SECRET_PATH"], vec!["--parent-pid", "2147483647"],
        vec!["--parent-pid", "+2"], vec!["--parent-pid", "02"], vec!["--parent-pid", "2", "--help"]] {
        let output = Command::new(env!("CARGO_BIN_EXE_rentgen-source-facts")).args(args)
            .stdin(Stdio::null()).output().unwrap();
        assert_eq!(output.status.code(), Some(2)); assert!(output.stdout.is_empty()); assert!(output.stderr.is_empty());
    }
}
#[test]
fn eof_is_required_and_watchdog_terminates_an_open_input_pipe() {
    use std::os::unix::process::ExitStatusExt;
    let mut child = start(); assert_eq!(read_frame(child.stdout.as_mut().unwrap()), HELLO);
    let mut input = child.stdin.take().unwrap(); input.write_all(&frame(ABSTENTION)).unwrap();
    // Retain input until after exit; wait_with_output must not manufacture EOF.
    let began = Instant::now(); let deadline = began + Duration::from_secs(7);
    loop {
        if child.try_wait().unwrap().is_some() { break; }
        if Instant::now() >= deadline { child.kill().unwrap(); child.wait().unwrap(); panic!("watchdog did not terminate"); }
        std::thread::sleep(Duration::from_millis(20));
    }
    let output = child.wait_with_output().unwrap(); drop(input);
    assert_eq!(output.status.signal(), Some(libc::SIGALRM));
    assert!(output.stdout.is_empty()); assert!(output.stderr.is_empty());
    assert!(began.elapsed() < Duration::from_secs(7));
}

// Runs only as a controlled subprocess of the ownership test. It is intentionally
// ignored in ordinary cargo test enumeration and has no source/fixture inputs.
#[test]
#[ignore]
fn source_facts_ownership_helper() {
    assert_eq!(std::env::var("RENTGEN_SOURCE_FACTS_OWNERSHIP_HELPER").as_deref(), Ok("1"));
    let mut child = start(); assert_eq!(read_frame(child.stdout.as_mut().unwrap()), HELLO);
    println!("\nOWNED_CHILD {}", child.id()); std::io::stdout().flush().unwrap();
    // Retain the owned child's input and launch thread. Test parent kills this helper.
    std::thread::sleep(Duration::from_secs(30));
    let _ = child.kill(); let _ = child.wait();
    panic!("ownership helper was not terminated");
}
struct Subreaper(libc::c_int);
impl Subreaper {
    fn new() -> Self {
        // SAFETY: one initialized c_int output and fixed prctl scalar arguments.
        // The test reaps only the exact verified grandchild, never arbitrary PIDs.
        unsafe {
            let mut previous = 0;
            assert_eq!(libc::prctl(libc::PR_GET_CHILD_SUBREAPER, &mut previous as *mut libc::c_int,0usize,0usize,0usize),0);
            assert_eq!(libc::prctl(libc::PR_SET_CHILD_SUBREAPER,1usize,0usize,0usize,0usize),0);
            Self(previous)
        }
    }
}
impl Drop for Subreaper {
    fn drop(&mut self) {
        // SAFETY: restore this test process's previous subreaper setting.
        unsafe { libc::prctl(libc::PR_SET_CHILD_SUBREAPER,self.0 as libc::c_ulong,0usize,0usize,0usize); }
    }
}
#[test]
fn death_of_launching_parent_kills_and_reaps_exact_owned_child() {
    let _subreaper = Subreaper::new();
    let mut helper = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "source_facts_ownership_helper", "--ignored", "--nocapture"])
        .env("RENTGEN_SOURCE_FACTS_OWNERSHIP_HELPER", "1")
        .stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
    let mut out = BufReader::new(helper.stdout.take().unwrap());
    let child_pid: libc::pid_t = loop {
        let mut line = String::new(); assert!(out.read_line(&mut line).unwrap() > 0);
        if let Some(pid) = line.trim().strip_prefix("OWNED_CHILD ") { break pid.parse().unwrap(); }
    };
    assert!(child_pid > 1);
    helper.kill().unwrap(); assert!(!helper.wait().unwrap().success());
    let end = Instant::now() + Duration::from_secs(2);
    loop {
        let mut status = 0;
        // SAFETY: wait only for the exact child adopted from our helper, using
        // initialized status storage. PID remains owned until this wait reaps it.
        let got = unsafe { libc::waitpid(child_pid, &mut status, libc::WNOHANG) };
        if got == child_pid {
            assert!(libc::WIFSIGNALED(status)); assert_eq!(libc::WTERMSIG(status),libc::SIGKILL); break;
        }
        assert_eq!(got,0);
        if Instant::now() >= end {
            // SAFETY: unreaped adopted child retains its verified PID; no reuse.
            unsafe { libc::kill(child_pid,libc::SIGKILL); libc::waitpid(child_pid,&mut status,0); }
            panic!("parent-death SIGKILL did not arrive before watchdog");
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    let mut rest = String::new(); out.read_to_string(&mut rest).unwrap();
    let mut err = vec![]; helper.stderr.take().unwrap().read_to_end(&mut err).unwrap(); assert!(err.is_empty());
}
