//! Experimental synthetic evidence engine. No provenance authentication or execution authority.
#![forbid(unsafe_code)]
mod catalog;
mod engine;
pub mod model;
mod parse;

pub const INPUT_LIMIT: usize = 65_536;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error { InvalidEnvelope, InputLimit }
impl Error {
    pub fn json(self) -> &'static [u8] {
        match self {
            Self::InvalidEnvelope => b"{\"error\":\"invalid_envelope\"}\n",
            Self::InputLimit => b"{\"error\":\"input_limit\"}\n",
        }
    }
}
/// Evaluate one complete bounded JSON envelope. All supplied authority is unverified.
/// The caller must authenticate provenance, own counters, and recheck disclosure access.
pub fn evaluate(input: &[u8]) -> Result<model::DiagnosticResult, Error> {
    let envelope = parse::parse(input)?;
    Ok(engine::evaluate(&envelope))
}
