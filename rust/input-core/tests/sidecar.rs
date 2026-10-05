#![cfg(target_os = "linux")]
use serde_json::{json, Value};
use std::io::{Read, Write};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

fn binary_path() -> std::path::PathBuf {
    std::env::var_os("RENTGEN_INPUT_CORE_TEST_BINARY").map(std::path::PathBuf::from)
        .unwrap_or_else(|| env!("CARGO_BIN_EXE_rentgen-input-core").into())
}
fn start() -> Child {
    Command::new(binary_path())
        .args(["--parent-pid", &std::process::id().to_string()])
        .env_clear().stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap()
}
fn recv(child: &mut Child) -> Value {
    let out=child.stdout.as_mut().unwrap(); let mut header=[0u8;4]; out.read_exact(&mut header).unwrap();
    let n=u32::from_le_bytes(header) as usize; assert!(n<=65536 && n>0);
    let mut b=vec![0;n]; out.read_exact(&mut b).unwrap(); serde_json::from_slice(&b).unwrap()
}
fn send(child:&mut Child,v:Value) {
    let b=serde_json::to_vec(&v).unwrap(); let input=child.stdin.as_mut().unwrap();
    input.write_all(&(b.len() as u32).to_le_bytes()).unwrap(); input.write_all(&b).unwrap(); input.flush().unwrap();
}
fn finish(child:&mut Child,success:bool) {
    let until=Instant::now()+Duration::from_secs(3);
    loop {
        if let Some(status)=child.try_wait().unwrap() {
            assert_eq!(status.success(),success);
            let mut extra=Vec::new(); child.stdout.as_mut().unwrap().read_to_end(&mut extra).unwrap(); assert!(extra.is_empty());
            let mut stderr=Vec::new(); child.stderr.as_mut().unwrap().read_to_end(&mut stderr).unwrap(); assert!(stderr.is_empty()); return;
        }
        if Instant::now()>until { let _=child.kill(); panic!("sidecar did not terminate"); }
        std::thread::sleep(Duration::from_millis(10));
    }
}
#[test]
fn hello_close_and_resource_caps() {
    let mut child=start();
    assert_eq!(recv(&mut child),json!({"protocol":1,"kind":"hello","implementation":"rentgen-input-core","contract":"submitted-zip-v1"}));
    let limits=std::fs::read_to_string(format!("/proc/{}/limits",child.id())).unwrap();
    let address=limits.lines().find(|l|l.starts_with("Max address space")).unwrap(); assert!(address.contains("134217728"));
    let core=limits.lines().find(|l|l.starts_with("Max core file size")).unwrap(); assert_eq!(core.split_whitespace().nth(4),Some("0"));
    send(&mut child,json!({"protocol":1,"seq":1,"op":"close"}));
    assert_eq!(recv(&mut child),json!({"protocol":1,"seq":1,"result":{"closed":true}})); finish(&mut child,true);
}
#[test]
fn parent_mismatch_exits_without_hello() {
    let mut child=Command::new(binary_path()).args(["--parent-pid","1"])
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap(); finish(&mut child,false);
}
#[test]
fn eof_and_malformed_oversize_frames_close_session() {
    let mut child=start(); recv(&mut child); drop(child.stdin.take()); finish(&mut child,false);
    let mut child=start(); recv(&mut child); child.stdin.as_mut().unwrap().write_all(&u32::MAX.to_le_bytes()).unwrap();
    assert_eq!(recv(&mut child)["error"]["code"],"LIMIT_EXCEEDED"); finish(&mut child,false);
    let mut child=start(); recv(&mut child); child.stdin.as_mut().unwrap().write_all(&[1,0]).unwrap(); drop(child.stdin.take());
    assert_eq!(recv(&mut child)["error"]["code"],"INVALID_REQUEST"); finish(&mut child,false);
}
#[test]
fn invalid_sequence_is_fatal_but_state_errors_can_close() {
    let mut child=start(); recv(&mut child); send(&mut child,json!({"protocol":1,"seq":2,"op":"close"}));
    assert_eq!(recv(&mut child)["error"]["code"],"INVALID_SEQUENCE"); finish(&mut child,false);
    let mut child=start(); recv(&mut child); send(&mut child,json!({"protocol":1,"seq":1,"op":"entries","offset":0,"limit":1}));
    assert_eq!(recv(&mut child)["error"]["code"],"INVALID_STATE");
    send(&mut child,json!({"protocol":1,"seq":2,"op":"close"})); assert_eq!(recv(&mut child)["result"]["closed"],true); finish(&mut child,true);
}
#[test]
fn failed_import_is_fatal_and_hides_source_path() {
    let mut child=start(); recv(&mut child);
    send(&mut child,json!({"protocol":1,"seq":1,"op":"open_import","path":"/does-not-exist/secret-name.zip","expected_sha256":"0".repeat(64)}));
    let response=recv(&mut child); assert_eq!(response["error"]["code"],"INVALID_PATH"); assert!(!response.to_string().contains("secret")); finish(&mut child,false);
}
#[test]
fn inherited_descriptor_is_closed_before_hello() {
    use std::os::fd::AsRawFd;
    let file=std::fs::File::open("/dev/null").unwrap();
    // SAFETY: this test owns the fd, and the immediately spawned process deliberately
    // inherits it to test the sidecar's close_range startup boundary.
    unsafe { assert!(libc::fcntl(file.as_raw_fd(),libc::F_SETFD,0)>=0); }
    let mut child=start(); recv(&mut child);
    assert!(!std::path::Path::new(&format!("/proc/{}/fd/{}",child.id(),file.as_raw_fd())).exists());
    send(&mut child,json!({"protocol":1,"seq":1,"op":"close"})); recv(&mut child); finish(&mut child,true);
}

#[test]
#[ignore = "helper launched only by parent_death_kills_owned_sidecar"]
fn parent_death_helper() {
    let marker=std::env::var("RENTGEN_PARENT_DEATH_MARKER").unwrap();
    let mut child=start(); recv(&mut child); std::fs::write(marker,child.id().to_string()).unwrap();
    std::thread::sleep(Duration::from_secs(30)); let _=child.kill(); let _=child.wait();
}
#[test]
fn parent_death_kills_owned_sidecar() {
    let marker=std::env::temp_dir().join(format!("rentgen-parent-death-{}",std::process::id()));
    let mut parent=Command::new(std::env::current_exe().unwrap()).args(["--ignored","--exact","parent_death_helper"])
        .env("RENTGEN_PARENT_DEATH_MARKER",&marker).stdout(Stdio::null()).stderr(Stdio::null()).spawn().unwrap();
    let until=Instant::now()+Duration::from_secs(3);
    let pid=loop {
        if let Ok(text)=std::fs::read_to_string(&marker) { if let Ok(pid)=text.parse::<u32>() { break pid; } }
        if Instant::now()>until { let _=parent.kill(); let _=parent.wait(); panic!("helper failed to start sidecar"); }
        std::thread::sleep(Duration::from_millis(10));
    };
    parent.kill().unwrap(); parent.wait().unwrap(); let _=std::fs::remove_file(&marker);
    let until=Instant::now()+Duration::from_secs(3);
    loop {
        // An orphan may remain a zombie until PID1 reaps it. Z/X confirms execution ended.
        let state=std::fs::read_to_string(format!("/proc/{pid}/stat"));
        if state.as_ref().map(|s|s.split(") ").nth(1).map(|x|x.starts_with('Z')||x.starts_with('X')).unwrap_or(false)).unwrap_or(true) { break; }
        assert!(Instant::now()<until,"sidecar survived parent death"); std::thread::sleep(Duration::from_millis(10));
    }
}
#[test]
#[ignore = "real 60-second absolute deadline qualification; run explicitly"]
fn absolute_session_deadline_terminates_partial_frame() {
    let start=Instant::now(); let mut child=start_child_for_deadline(); recv(&mut child);
    child.stdin.as_mut().unwrap().write_all(&[1,0]).unwrap();
    loop {
        if let Some(status)=child.try_wait().unwrap() { assert!(!status.success()); break; }
        if start.elapsed()>Duration::from_secs(63) { let _=child.kill(); panic!("absolute deadline not enforced"); }
        std::thread::sleep(Duration::from_millis(50));
    }
    assert!(start.elapsed()>=Duration::from_secs(59));
}
fn start_child_for_deadline()->Child { start() }
