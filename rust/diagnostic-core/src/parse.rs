//! Strict bounded JSON admission. Error details never leave this module.
use crate::{catalog, model::*, Error, INPUT_LIMIT};
use serde::de::{self, DeserializeSeed, MapAccess, SeqAccess, Visitor};
use serde::Deserializer;
use serde_json::{Map, Value as Json};
use std::{collections::BTreeSet, fmt};

struct StrictJson { depth: u8 }
impl<'de> DeserializeSeed<'de> for StrictJson {
    type Value = Json;
    fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Json, D::Error> {
        if self.depth > 16 { return Err(de::Error::custom("invalid")); }
        d.deserialize_any(self)
    }
}
impl<'de> Visitor<'de> for StrictJson {
    type Value = Json;
    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { f.write_str("bounded JSON") }
    fn visit_bool<E: de::Error>(self, v: bool) -> Result<Json, E> { Ok(Json::Bool(v)) }
    fn visit_u64<E: de::Error>(self, v: u64) -> Result<Json, E> { Ok(Json::Number(v.into())) }
    fn visit_str<E: de::Error>(self, v: &str) -> Result<Json, E> { Ok(Json::String(v.to_owned())) }
    fn visit_string<E: de::Error>(self, v: String) -> Result<Json, E> { Ok(Json::String(v)) }
    fn visit_unit<E: de::Error>(self) -> Result<Json, E> { Ok(Json::Null) }
    fn visit_none<E: de::Error>(self) -> Result<Json, E> { Ok(Json::Null) }
    // No signed/floating visitors: -0, fractions and exponent tokens fail closed.
    fn visit_seq<A: SeqAccess<'de>>(self, mut a: A) -> Result<Json, A::Error> {
        let mut result = Vec::new();
        while let Some(v) = a.next_element_seed(StrictJson { depth: self.depth + 1 })? { result.push(v); }
        Ok(Json::Array(result))
    }
    fn visit_map<A: MapAccess<'de>>(self, mut a: A) -> Result<Json, A::Error> {
        let mut result = Map::new();
        while let Some(key) = a.next_key::<String>()? {
            if result.contains_key(&key) { return Err(de::Error::custom("invalid")); }
            let value = a.next_value_seed(StrictJson { depth: self.depth + 1 })?;
            result.insert(key, value);
        }
        Ok(Json::Object(result))
    }
}

pub(crate) fn parse(input: &[u8]) -> Result<Envelope, Error> {
    if input.len() > INPUT_LIMIT { return Err(Error::InputLimit); }
    let mut deserializer = serde_json::Deserializer::from_slice(input);
    let value = StrictJson { depth: 1 }.deserialize(&mut deserializer).map_err(|_| Error::InvalidEnvelope)?;
    deserializer.end().map_err(|_| Error::InvalidEnvelope)?;
    enforce_object_shapes(&value)?;
    let envelope: Envelope = serde_json::from_value(value).map_err(|_| Error::InvalidEnvelope)?;
    validate(&envelope)?;
    Ok(envelope)
}
// Serde's derived structs also support positional sequences in some formats.
// The public protocol permits only JSON objects for every record, not those
// alternate representations. Validate the entire record graph before conversion.
fn enforce_object_shapes(value: &Json) -> Result<(), Error> {
    let object = |v: &Json| if v.is_object() { Ok(()) } else { Err(Error::InvalidEnvelope) };
    let tagged = |v: &Json| if v.is_object() && v.get("kind").is_some_and(Json::is_string) {
        Ok(())
    } else { Err(Error::InvalidEnvelope) };
    object(value)?;
    object(&value["scope"])?; object(&value["budget"])?; tagged(&value["target"])?;
    let capabilities = value["capabilities"].as_array().ok_or(Error::InvalidEnvelope)?;
    let facts = value["facts"].as_array().ok_or(Error::InvalidEnvelope)?;
    if capabilities.len() > 6 || facts.len() > 128 { return Err(Error::InvalidEnvelope); }
    for capability in capabilities { object(capability)?; }
    for fact in facts {
        object(fact)?; object(&fact["scope"])?; tagged(&fact["target"])?; tagged(&fact["value"])?;
    }
    Ok(())
}
fn ids_valid(scope: &Scope, target: &Target) -> bool {
    let scope_ids = [scope.case_id, scope.snapshot_id, scope.revision_id, scope.session_id, scope.context_id];
    let target_ids: Vec<u16> = match target {
        Target::Call { site, module, method, .. } => vec![*site, *module, *method],
        Target::Receiver { site, receiver, member, .. } => vec![*site, *receiver, *member],
        Target::Mismatch { site, receiver, member, source_type, runtime_type } => vec![*site, *receiver, *member, *source_type, *runtime_type],
    };
    scope_ids.iter().chain(target_ids.iter()).all(|id| *id != 0)
}
fn unique<T: Ord + Copy>(values: impl IntoIterator<Item=T>) -> bool {
    let mut seen = BTreeSet::new(); values.into_iter().all(|v| seen.insert(v))
}
fn valid_pair(f: &Fact) -> bool {
    use Predicate as P;
    let value_valid = match (&f.predicate, &f.value) {
        (P::CallEdge, Value::Edge { .. }) | (P::ReceiverKind, Value::ReceiverKind { .. })
        | (P::SourceMember, Value::SourcePresence { .. }) | (P::ObjectCorrelation, Value::Correlation { .. }) => true,
        (P::CompiledCopyPresent | P::ContextEnabled | P::Exported | P::ReceiverRetained | P::ServerCallEnabled, Value::Bool { .. }) => true,
        (P::MemberPresent, Value::Shape { receiver_kind, witness, .. }) => catalog::witness(*receiver_kind) == Some(*witness),
        _ => false,
    };
    let target_valid = match f.target {
        Target::Call { .. } => matches!(f.predicate, P::CallEdge | P::CompiledCopyPresent | P::ContextEnabled | P::Exported | P::ServerCallEnabled),
        Target::Receiver { .. } => matches!(f.predicate, P::ReceiverRetained | P::ReceiverKind | P::MemberPresent),
        Target::Mismatch { .. } => matches!(f.predicate, P::ReceiverRetained | P::ReceiverKind | P::MemberPresent | P::SourceMember | P::ObjectCorrelation),
    };
    value_valid && target_valid
}
pub(crate) fn validate(e: &Envelope) -> Result<(), Error> {
    let invalid = || Error::InvalidEnvelope;
    if (e.schema_version, e.rule_version, e.catalog_version) != (1, 1, 1)
        || !ids_valid(&e.scope, &e.target) || e.facts.len() > 128 || e.capabilities.len() > 6
        || e.attempted_checks.len() > 3 || e.budget.observations_remaining > 3
        || e.budget.cost_remaining > 9 || e.budget.rule_applications_remaining > 256
        || usize::from(e.budget.observations_remaining) + e.attempted_checks.len() > 3
        || u16::from(e.budget.cost_remaining) + e.attempted_checks.iter().map(|c| u16::from(catalog::cost(*c))).sum::<u16>() > 9
        || !unique(e.facts.iter().map(|f| f.id)) || !unique(e.capabilities.iter().map(|c| c.check_id))
        || !unique(e.attempted_checks.iter().copied()) || e.facts.iter().map(|f| f.supersedes.len()).sum::<usize>() > 128 {
        return Err(invalid());
    }
    for f in &e.facts {
        if f.id == 0 || f.input_id == 0 || !ids_valid(&f.scope, &f.target) || f.adapter_version != 1
            || f.sequence > f.valid_until || !valid_pair(f) || !unique(f.supersedes.iter().copied()) {
            return Err(invalid());
        }
        if let Some(check) = f.check_id {
            if !e.attempted_checks.contains(&check) || !catalog::outputs(check).contains(&f.predicate) { return Err(invalid()); }
        }
        if !f.supersedes.is_empty() && (f.sequence > e.sequence || f.adapter != Adapter::Synthetic
            || !matches!(f.state, FactState::Observed | FactState::Stale | FactState::Revoked)) { return Err(invalid()); }
        for id in &f.supersedes {
            let old = e.facts.iter().find(|old| old.id == *id).ok_or_else(invalid)?;
            if old.adapter != f.adapter || old.adapter_version != f.adapter_version || old.scope != f.scope
                || old.target != f.target || old.predicate != f.predicate || old.sequence >= f.sequence { return Err(invalid()); }
        }
    }
    Ok(())
}
