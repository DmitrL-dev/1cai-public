use serde::{Deserialize, Deserializer, Serialize};

macro_rules! enums {
    ($name:ident { $($variant:ident => $label:literal),+ $(,)? }) => {
        #[derive(Clone, Copy, Debug, Serialize, PartialEq, Eq, PartialOrd, Ord)]
        pub enum $name { $(#[serde(rename = $label)] $variant),+ }
        impl $name {
            pub fn as_str(self) -> &'static str { match self { $(Self::$variant => $label),+ } }
        }
        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
                struct StringOnly;
                impl<'de> serde::de::Visitor<'de> for StringOnly {
                    type Value = $name;
                    fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                        f.write_str("catalog string")
                    }
                    fn visit_str<E: serde::de::Error>(self, value: &str) -> Result<Self::Value, E> {
                        match value { $($label => Ok($name::$variant),)+ _ => Err(E::custom("invalid")) }
                    }
                }
                deserializer.deserialize_str(StringOnly)
            }
        }
    };
}
enums!(Platform { Synthetic => "synthetic_8_3_27", Unsupported => "unsupported" });
enums!(Compatibility { Synthetic => "synthetic_v1", Unsupported => "unsupported" });
enums!(Execution { Server => "server", ThinClient => "thin_client", Unknown => "unknown" });
enums!(ModuleKind { Common => "common", Form => "form" });
enums!(Route { Dynamic => "dynamic", SameContext => "same_context", ServerBridge => "server_bridge" });
enums!(ReceiverKind {
    ApplicationObject => "application_object", Other => "other", QueryResult => "query_result",
    QuerySelection => "query_selection", Structure => "structure"
});
enums!(Access { Revoked => "revoked", Usable => "usable" });
enums!(CapabilityState { ConsentRequired => "consent_required", Ready => "ready", Unavailable => "unavailable" });
enums!(FactState { Conflicting => "conflicting", Observed => "observed", Revoked => "revoked", Stale => "stale", Unavailable => "unavailable" });
enums!(Adapter { Synthetic => "synthetic_v1", Untrusted => "untrusted", UnverifiedZip => "unverified_zip" });
enums!(Edge { Dynamic => "dynamic", StaticExternalResolved => "static_external_resolved", Unresolved => "unresolved" });
enums!(ShapeWitness { KeyPresence => "key_presence", QuerySchema => "query_schema", SessionMetadata => "session_metadata" });
enums!(SourcePresence { AbsentComplete => "absent_complete", Present => "present", Unresolved => "unresolved" });
enums!(Correlation { DifferentAttested => "different_attested", SameAttested => "same_attested", Unverified => "unverified" });
enums!(Predicate {
    CallEdge => "call_edge", CompiledCopyPresent => "compiled_copy_present", ContextEnabled => "context_enabled",
    Exported => "exported", MemberPresent => "member_present", ObjectCorrelation => "object_correlation",
    ReceiverKind => "receiver_kind", ReceiverRetained => "receiver_retained", ServerCallEnabled => "server_call_enabled",
    SourceMember => "source_member"
});
enums!(CheckId {
    CallCopy => "c01_call_copy", CallFlags => "c02_call_flags", ReceiverKind => "c10_receiver_kind",
    ReceiverShape => "c11_receiver_shape", SourcePresence => "c20_source_presence", ObjectCorrelation => "c21_object_correlation"
});
enums!(HypothesisId {
    CallContextUnavailable => "call_context_unavailable", ImmediateMemberAbsent => "immediate_member_absent",
    MethodNotExported => "method_not_exported", ReceiverKindMismatch => "receiver_kind_mismatch",
    SourceRuntimeMismatch => "source_runtime_mismatch"
});
enums!(State { Refuted => "refuted", Supported => "supported", Unknown => "unknown" });

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Scope {
    pub case_id: u16, pub snapshot_id: u16, pub revision_id: u16,
    pub session_id: u16, pub context_id: u16,
    pub platform: Platform, pub compatibility: Compatibility, pub execution: Execution,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Target {
    Call { site: u16, module: u16, method: u16, module_kind: ModuleKind, route: Route },
    Receiver { site: u16, receiver: u16, member: u16, expected_kind: ReceiverKind },
    Mismatch { site: u16, receiver: u16, member: u16, source_type: u16, runtime_type: u16 },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Value {
    Bool { value: bool }, Edge { value: Edge }, ReceiverKind { value: ReceiverKind },
    Shape { present: bool, receiver_kind: ReceiverKind, witness: ShapeWitness },
    SourcePresence { value: SourcePresence }, Correlation { value: Correlation },
}
impl Value {
    pub fn resolved(&self) -> bool {
        !matches!(self, Self::SourcePresence { value: SourcePresence::Unresolved }
            | Self::Correlation { value: Correlation::Unverified }
            | Self::Edge { value: Edge::Dynamic | Edge::Unresolved })
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Budget {
    pub observations_remaining: u8, pub cost_remaining: u8, pub rule_applications_remaining: u16,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Capability { pub check_id: CheckId, pub state: CapabilityState }

fn nullable_check<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Option<CheckId>, D::Error> {
    Option::<CheckId>::deserialize(deserializer)
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Fact {
    pub id: u16, pub scope: Scope, pub target: Target, pub predicate: Predicate, pub value: Value,
    pub state: FactState, pub adapter: Adapter, pub adapter_version: u16, pub input_id: u16,
    #[serde(deserialize_with = "nullable_check")]
    pub check_id: Option<CheckId>,
    pub sequence: u16, pub valid_until: u16, pub supersedes: Vec<u16>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    pub schema_version: u16, pub rule_version: u16, pub catalog_version: u16,
    pub scope: Scope, pub target: Target, pub sequence: u16, pub access: Access, pub cancelled: bool,
    pub budget: Budget, pub attempted_checks: Vec<CheckId>, pub capabilities: Vec<Capability>, pub facts: Vec<Fact>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Hypothesis {
    pub id: HypothesisId, pub state: State, pub rule_id: &'static str,
    pub evidence_ids: Vec<u16>, pub unknown_reasons: Vec<&'static str>, pub missing_predicates: Vec<Predicate>,
}
#[derive(Clone, Debug, Default, Serialize)]
pub struct Trace { pub contributing_ids: Vec<u16>, pub excluded: Vec<Excluded> }
#[derive(Clone, Debug, Serialize)]
pub struct Excluded { pub fact_id: u16, pub reasons: Vec<&'static str> }
#[derive(Clone, Debug, Serialize)]
pub struct OutcomeFact { pub predicate: Predicate, pub value: Value }
#[derive(Clone, Debug, Serialize)]
pub struct Outcome { pub outcome_id: u8, pub facts: Vec<OutcomeFact> }
#[derive(Clone, Debug, Serialize)]
pub struct Candidate {
    pub check_id: CheckId, pub pair_score: u8, pub resolve_score: u8,
    pub observation_charge: u8, pub max_disclosed_facts: u8, pub cost: u8,
    pub consent: &'static str, pub prerequisite_fact_ids: Vec<u16>,
    pub affected_hypotheses: Vec<HypothesisId>, pub missing_predicates: Vec<Predicate>, pub outcomes: Vec<Outcome>,
}
#[derive(Clone, Debug, Serialize)]
pub struct BlockedCheck { pub check_id: CheckId, pub reasons: Vec<&'static str> }
#[derive(Clone, Debug, Serialize)]
pub struct DiagnosticResult {
    pub schema_version: u16, pub rule_version: u16, pub catalog_version: u16,
    pub assurance: &'static str, pub kind: &'static str, pub stop: &'static str,
    pub hypotheses: Vec<Hypothesis>, pub supported: Vec<HypothesisId>, pub trace: Trace,
    pub candidates: Vec<Candidate>, pub selected_check: Option<Candidate>, pub blocked_checks: Vec<BlockedCheck>,
    pub rule_applications_used: u16,
}
