//! One synthetic request, bounded stdin; no arguments or environment configuration.
#![forbid(unsafe_code)]
use rentgen_diagnostic_core::{evaluate, Error, INPUT_LIMIT};
use std::io::{self, Read, Write};
fn run() -> Result<(), Error> {
    let mut bytes = Vec::new();
    io::stdin().lock().take((INPUT_LIMIT + 1) as u64).read_to_end(&mut bytes).map_err(|_| Error::InvalidEnvelope)?;
    let result = evaluate(&bytes)?;
    let mut serialized = serde_json::to_vec(&result).map_err(|_| Error::InvalidEnvelope)?;
    serialized.push(b'\n');
    io::stdout().lock().write_all(&serialized).map_err(|_| Error::InvalidEnvelope)
}
fn main() {
    if let Err(error) = run() {
        let _ = io::stdout().lock().write_all(error.json());
        std::process::exit(2);
    }
}
