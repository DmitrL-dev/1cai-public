//! Closed source-only records. Local IDs are references, never attestations.
use serde::{Deserialize, Deserializer, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(transparent)]
pub struct Id(u32);
impl Id {
    pub fn get(self) -> u32 { self.0 }
}
impl<'de> Deserialize<'de> for Id {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let n = u32::deserialize(d)?;
        if (1..=2_147_483_647).contains(&n) { Ok(Self(n)) }
        else { Err(serde::de::Error::custom("invalid")) }
    }
}
// Explicit deserialize_with prevents serde's missing-Option default: null is
// admitted, but the nullable field itself is always required on this protocol.
fn nullable<'de, D, T>(d: D) -> Result<Option<T>, D::Error>
where D: Deserializer<'de>, T: Deserialize<'de> { Option::<T>::deserialize(d) }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Profile { #[serde(rename = "submitted_source_facts_v1")] SubmittedSourceFactsV1 }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum RuleSet { #[serde(rename = "source_observations_v1")] SourceObservationsV1 }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Unknown { #[serde(rename = "unknown")] Unknown }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Assurance {
    #[serde(rename = "source_facts_host_asserted_no_binding_no_runtime")]
    HostAssertedNoBindingNoRuntime,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SelectorValue { #[serde(rename = "qualified_selector")] QualifiedSelector }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SelectorUnavailable {
    InvalidUtf8, InvalidBom, ForbiddenControl, InvalidLineEnding,
    UnsupportedCodeCharacter, IdentifierLimit, TokenBytesLimit, TokenCountLimit,
    InvalidNumber, UnsupportedLiteral, UnterminatedString, MultilineString,
    UnsupportedKeyword, UnsupportedTopLevel, InvalidHeader, DuplicateParameter,
    ParameterLimit, DuplicateRoutine, RoutineLimit, NestedRoutine,
    MismatchedTerminator, MissingTerminator, StrayStructuralKeyword,
    UnbalancedDelimiter, DelimiterDepthLimit, SelectorSpanInvalid,
    SelectorNotQualified, SelectorOutsideBody, SelectorChained,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExportUnavailable {
    SelectorUnavailable, CandidateIdentityUnavailable, CandidateNameMismatch,
    CandidateNotAdmitted, DeclarationUnavailable,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServerUnavailable {
    SelectorUnavailable, CandidateNameMismatch, XmlMissing, XmlLimit,
    XmlForbidden, XmlInvalid, XmlShapeUnsupported, XmlDuplicateContainer,
    XmlNameMissing, XmlNameDuplicate, XmlNameInvalid, XmlServerMissing,
    XmlServerDuplicate, XmlServerInvalid,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Scope {
    pub case_id: Id,
    pub input_id: Id,
    pub selector_id: Id,
    pub caller_entry_id: Id,
    pub candidate_entry_id: Id,
    #[serde(deserialize_with = "nullable")]
    pub xml_entry_id: Option<Id>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum SelectorObservation {
    Observed { value: SelectorValue, receipt_id: Id },
    Unavailable { reason: SelectorUnavailable },
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum ExportObservation {
    Observed { value: bool, receipt_id: Id, header_id: Id },
    Unavailable { reason: ExportUnavailable },
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum ServerObservation {
    Observed { value: bool, receipt_id: Id, property_id: Id },
    Unavailable { reason: ServerUnavailable },
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observations {
    pub selector: SelectorObservation,
    pub export: ExportObservation,
    pub server: ServerObservation,
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct SelectorReceipt {
    pub receipt_id: Id, pub case_id: Id, pub input_id: Id, pub selector_id: Id,
    pub entry_id: Id,
}
#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct ExportReceipt {
    pub receipt_id: Id, pub case_id: Id, pub input_id: Id, pub selector_id: Id,
    pub entry_id: Id, pub header_id: Id,
}
#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct ServerReceipt {
    pub receipt_id: Id, pub case_id: Id, pub input_id: Id, pub selector_id: Id,
    pub entry_id: Id, pub property_id: Id,
}
#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Receipts {
    #[serde(deserialize_with = "nullable")]
    pub selector: Option<SelectorReceipt>,
    #[serde(deserialize_with = "nullable")]
    pub export: Option<ExportReceipt>,
    #[serde(deserialize_with = "nullable")]
    pub server: Option<ServerReceipt>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Envelope {
    pub schema_version: u8,
    pub profile: Profile,
    pub rule_set: RuleSet,
    pub scope: Scope,
    pub observations: Observations,
    pub receipts: Receipts,
    pub receiver_binding: Unknown,
    pub runtime_relation: Unknown,
}

/// Validated host assertions only. No source, binding or runtime authentication.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct SourceFactsResult {
    pub schema_version: u8,
    pub profile: Profile,
    pub rule_set: RuleSet,
    pub assurance: Assurance,
    pub scope: Scope,
    pub observations: Observations,
    pub receiver_binding: Unknown,
    pub runtime_relation: Unknown,
}
