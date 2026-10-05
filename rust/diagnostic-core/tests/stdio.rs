use std::io::Write;
use std::process::{Command, Stdio};
fn run(input: &[u8]) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_rentgen-diagnostic-core"))
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().unwrap();
    child.stdin.take().unwrap().write_all(input).unwrap(); child.wait_with_output().unwrap()
}
#[test]
fn malformed_input_is_non_echoing_and_stderr_empty() {
    let output = run(b"{\"private_path\":\"CANARY_SECRET_42\"}");
    assert!(!output.status.success()); assert_eq!(output.stdout, b"{\"error\":\"invalid_envelope\"}\n"); assert!(output.stderr.is_empty());
}
#[test]
fn oversized_input_is_rejected_not_truncated() {
    let output = run(&vec![b' '; 65_537]); assert!(!output.status.success());
    assert_eq!(output.stdout, b"{\"error\":\"input_limit\"}\n"); assert!(output.stderr.is_empty());
}
