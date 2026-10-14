//! Three submitted lexical/header/XML observations, never a call diagnosis.
//! This pure entry point performs no IO and authenticates no host assertions.
mod model;
mod parse;
pub use model::{Assurance, ExportObservation, ExportUnavailable, Id, Observations,
    Profile, RuleSet, Scope, SelectorObservation, SelectorUnavailable, SelectorValue,
    ServerObservation, ServerUnavailable, SourceFactsResult, Unknown};
use model::Envelope;

pub const INPUT_LIMIT: usize = 65_536;
pub const OUTPUT_LIMIT: usize = 65_536;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error { InvalidEnvelope, InputLimit }

fn validate(e: &Envelope) -> Result<(), Error> {
    let invalid = Error::InvalidEnvelope;
    let scope = e.scope;
    if e.schema_version != 2 || scope.xml_entry_id.is_some_and(|id|
        id == scope.caller_entry_id || id == scope.candidate_entry_id) { return Err(invalid); }
    let scoped = |case, input, selector| (case, input, selector) ==
        (scope.case_id, scope.input_id, scope.selector_id);
    match (e.observations.selector, e.receipts.selector) {
        (SelectorObservation::Observed { receipt_id, .. }, Some(r))
            if receipt_id == r.receipt_id && scoped(r.case_id, r.input_id, r.selector_id)
                && r.entry_id == scope.caller_entry_id => (),
        (SelectorObservation::Unavailable { .. }, None) => (),
        _ => return Err(invalid),
    }
    match (e.observations.export, e.receipts.export) {
        (ExportObservation::Observed { receipt_id, header_id, .. }, Some(r))
            if receipt_id == r.receipt_id && header_id == r.header_id
                && scoped(r.case_id, r.input_id, r.selector_id)
                && r.entry_id == scope.candidate_entry_id => (),
        (ExportObservation::Unavailable { .. }, None) => (),
        _ => return Err(invalid),
    }
    match (e.observations.server, e.receipts.server) {
        (ServerObservation::Observed { receipt_id, property_id, .. }, Some(r))
            if receipt_id == r.receipt_id && property_id == r.property_id
                && scoped(r.case_id, r.input_id, r.selector_id)
                && Some(r.entry_id) == scope.xml_entry_id => (),
        (ServerObservation::Unavailable { .. }, None) => (),
        _ => return Err(invalid),
    }
    let ids = [e.receipts.selector.map(|r| r.receipt_id),
        e.receipts.export.map(|r| r.receipt_id), e.receipts.server.map(|r| r.receipt_id)];
    for i in 0..ids.len() {
        if ids[i].is_some() && ids[i+1..].contains(&ids[i]) { return Err(invalid); }
    }
    use ExportObservation as E;
    use ExportUnavailable as ER;
    use SelectorObservation as Q;
    use ServerObservation as S;
    use ServerUnavailable as SR;
    // Exhaustive protocol dependency matrix. Unknown combinations do not pass.
    let valid = match (e.observations.selector, e.observations.export,
                       e.observations.server, scope.xml_entry_id) {
        (Q::Unavailable { .. }, E::Unavailable { reason: ER::SelectorUnavailable },
            S::Unavailable { reason: SR::SelectorUnavailable }, _) => true,
        (Q::Observed { .. }, E::Unavailable { reason: ER::CandidateIdentityUnavailable },
            S::Unavailable { reason: SR::XmlMissing }, None) => true,
        (Q::Observed { .. }, E::Unavailable { reason: ER::CandidateIdentityUnavailable },
            S::Unavailable { reason: SR::XmlLimit | SR::XmlForbidden | SR::XmlInvalid |
                SR::XmlShapeUnsupported | SR::XmlDuplicateContainer | SR::XmlNameMissing |
                SR::XmlNameDuplicate | SR::XmlNameInvalid }, Some(_)) => true,
        (Q::Observed { .. }, E::Unavailable { reason: ER::CandidateNameMismatch },
            S::Unavailable { reason: SR::CandidateNameMismatch }, Some(_)) => true,
        (Q::Observed { .. }, E::Observed { .. } | E::Unavailable {
                reason: ER::CandidateNotAdmitted | ER::DeclarationUnavailable },
            S::Observed { .. } | S::Unavailable { reason: SR::XmlServerMissing |
                SR::XmlServerDuplicate | SR::XmlServerInvalid }, Some(_)) => true,
        _ => false,
    };
    if !valid || (scope.caller_entry_id == scope.candidate_entry_id && matches!(
        e.observations.export, E::Unavailable { reason: ER::CandidateNotAdmitted })) {
        return Err(invalid);
    }
    Ok(())
}

/// Admit one complete bounded JSON envelope and preserve its three observations.
/// Receipt checks establish local consistency only; a caller can fabricate them.
pub fn evaluate(input: &[u8]) -> Result<SourceFactsResult, Error> {
    let e = parse::parse(input)?;
    validate(&e)?;
    Ok(SourceFactsResult {
        schema_version: 2, profile: e.profile, rule_set: e.rule_set,
        assurance: Assurance::HostAssertedNoBindingNoRuntime,
        scope: e.scope, observations: e.observations,
        receiver_binding: e.receiver_binding, runtime_relation: e.runtime_relation,
    })
}
