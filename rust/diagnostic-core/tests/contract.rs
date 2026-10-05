//! Public development examples only. Independent evaluation lives outside this crate.
use rentgen_diagnostic_core::{evaluate, model::*, Error, INPUT_LIMIT};
use serde_json::{json, Value as Json};

fn case() -> Envelope {
    let mut e = Envelope {
        schema_version: 1, rule_version: 1, catalog_version: 1,
        scope: Scope { case_id: 1, snapshot_id: 2, revision_id: 3, session_id: 4, context_id: 5,
            platform: Platform::Synthetic, compatibility: Compatibility::Synthetic, execution: Execution::ThinClient },
        target: Target::Call { site: 1, module: 2, method: 3, module_kind: ModuleKind::Common, route: Route::SameContext },
        sequence: 1, access: Access::Usable, cancelled: false,
        budget: Budget { observations_remaining: 3, cost_remaining: 9, rule_applications_remaining: 256 },
        attempted_checks: vec![], capabilities: vec![
            Capability { check_id: CheckId::CallCopy, state: CapabilityState::Ready },
            Capability { check_id: CheckId::CallFlags, state: CapabilityState::Ready },
        ], facts: vec![],
    };
    add(&mut e, Predicate::CallEdge, Value::Edge { value: Edge::StaticExternalResolved }); e
}
fn add(e: &mut Envelope, predicate: Predicate, value: Value) -> u16 {
    let id = e.facts.iter().map(|f| f.id).max().unwrap_or(0) + 1;
    e.facts.push(Fact { id, scope: e.scope.clone(), target: e.target.clone(), predicate, value,
        state: FactState::Observed, adapter: Adapter::Synthetic, adapter_version: 1, input_id: id, check_id: None,
        sequence: e.sequence, valid_until: 100, supersedes: vec![] }); id
}
fn bit(e: &mut Envelope, predicate: Predicate, value: bool) -> u16 { add(e, predicate, Value::Bool { value }) }
fn result(e: &Envelope) -> DiagnosticResult { evaluate(&serde_json::to_vec(e).unwrap()).unwrap() }
fn state(e: &Envelope, id: HypothesisId) -> State { result(e).hypotheses.into_iter().find(|h| h.id == id).unwrap().state }
fn receiver(kind: ReceiverKind) -> Envelope {
    let mut e = case(); e.target = Target::Receiver { site: 1, receiver: 2, member: 3, expected_kind: kind }; e.facts.clear();
    bit(&mut e, Predicate::ReceiverRetained, true);
    e.capabilities = vec![Capability { check_id: CheckId::ReceiverKind, state: CapabilityState::Ready },
        Capability { check_id: CheckId::ReceiverShape, state: CapabilityState::Ready }]; e
}
fn shape(e: &mut Envelope, kind: ReceiverKind, present: bool) {
    let witness = match kind { ReceiverKind::Structure => ShapeWitness::KeyPresence,
        ReceiverKind::ApplicationObject => ShapeWitness::SessionMetadata, _ => ShapeWitness::QuerySchema };
    add(e, Predicate::MemberPresent, Value::Shape { present, receiver_kind: kind, witness });
}
fn mismatch() -> Envelope {
    let mut e = receiver(ReceiverKind::ApplicationObject);
    e.target = Target::Mismatch { site: 1, receiver: 2, member: 3, source_type: 10, runtime_type: 11 };
    e.facts.clear(); bit(&mut e, Predicate::ReceiverRetained, true);
    e.capabilities.extend([Capability { check_id: CheckId::SourcePresence, state: CapabilityState::Ready },
        Capability { check_id: CheckId::ObjectCorrelation, state: CapabilityState::Ready }]); e
}

#[test]
fn declared_selector_and_disclosure_costs() {
    let r = result(&case());
    assert_eq!(r.kind, "check_request");
    let c = r.selected_check.unwrap(); assert_eq!(c.check_id, CheckId::CallFlags);
    assert_eq!((c.pair_score, c.resolve_score, c.max_disclosed_facts, c.cost), (1, 2, 3, 3));
    assert_eq!(c.outcomes.len(), 8); assert!(c.outcomes.iter().all(|o| o.facts.len() == 3));
    assert_eq!(r.rule_applications_used, 22);
}
#[test]
fn known_values_cannot_manufacture_reread_gain() {
    let mut e = case(); bit(&mut e, Predicate::CompiledCopyPresent, true);
    let r = result(&e);
    assert!(!r.candidates.iter().any(|c| c.check_id == CheckId::CallCopy));
    assert!(r.blocked_checks.iter().any(|c| c.check_id == CheckId::CallCopy && c.reasons.contains(&"no_status_change")));
}
#[test]
fn flags_outcomes_preserve_already_known_bits() {
    let mut e = case(); bit(&mut e, Predicate::Exported, true);
    let flags = result(&e).candidates.into_iter().find(|c| c.check_id == CheckId::CallFlags).unwrap();
    assert_eq!(flags.outcomes.len(), 4);
    assert!(flags.outcomes.iter().all(|o| o.outcome_id & 1 == 1));
}
#[test]
fn coexisting_findings_are_not_exclusive_causes() {
    let mut e = case(); bit(&mut e, Predicate::ContextEnabled, false); bit(&mut e, Predicate::Exported, false);
    let r = result(&e); assert_eq!(r.kind, "diagnosis");
    assert_eq!(r.supported, vec![HypothesisId::CallContextUnavailable, HypothesisId::MethodNotExported]);
}
#[test]
fn missing_competitor_never_proves_the_last_hypothesis() {
    let mut e = case(); bit(&mut e, Predicate::Exported, true);
    assert_eq!(state(&e, HypothesisId::CallContextUnavailable), State::Unknown);
    assert_eq!(result(&e).kind, "check_request");
}
#[test]
fn unresolved_anchor_cannot_be_recreated() {
    let mut e = case(); e.facts.clear(); let r = result(&e);
    assert_eq!(r.stop, "missing_anchor"); assert!(r.selected_check.is_none());
    assert!(r.hypotheses.iter().all(|h| h.state == State::Unknown && h.evidence_ids.is_empty()));
}
#[test]
fn conflict_overrides_other_sufficient_premise_only_in_its_dependencies() {
    let mut e = case(); bit(&mut e, Predicate::ContextEnabled, false); bit(&mut e, Predicate::CompiledCopyPresent, true);
    bit(&mut e, Predicate::CompiledCopyPresent, false); bit(&mut e, Predicate::Exported, false);
    let r = result(&e);
    assert_eq!(r.supported, vec![HypothesisId::MethodNotExported]);
    assert_eq!(state(&e, HypothesisId::CallContextUnavailable), State::Unknown);
}
#[test]
fn explicit_conflict_has_authority_but_never_witness_ids() {
    let mut e = case(); let id = bit(&mut e, Predicate::Exported, false); e.facts.last_mut().unwrap().state = FactState::Conflicting;
    let r = result(&e); assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Unknown);
    assert!(!r.trace.contributing_ids.contains(&id));
    assert!(r.trace.excluded.iter().any(|f| f.fact_id == id && f.reasons.contains(&"conflicting")));
}
#[test]
fn replacement_is_explicit_and_revocation_does_not_resurrect() {
    let mut e = case(); let a = bit(&mut e, Predicate::Exported, true); let b = bit(&mut e, Predicate::Exported, false);
    assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Unknown);
    e.sequence = 2; bit(&mut e, Predicate::Exported, false); e.facts.last_mut().unwrap().supersedes = vec![a, b];
    assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Supported);
    e.facts.last_mut().unwrap().state = FactState::Revoked;
    assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Unknown);
    assert_eq!(result(&e).trace.excluded.iter().filter(|f| f.reasons.contains(&"superseded")).count(), 2);
}
#[test]
fn future_replacement_cannot_remove_one_side_of_current_conflict() {
    let mut e = case(); let a = bit(&mut e, Predicate::Exported, true); bit(&mut e, Predicate::Exported, false);
    bit(&mut e, Predicate::Exported, false); let f = e.facts.last_mut().unwrap(); f.sequence = 2; f.supersedes = vec![a];
    assert_eq!(evaluate(&serde_json::to_vec(&e).unwrap()).unwrap_err(), Error::InvalidEnvelope);
}
#[test]
fn stale_and_foreign_evidence_never_support() {
    let mut e = case(); bit(&mut e, Predicate::Exported, false);
    e.facts.last_mut().unwrap().valid_until = 1; e.sequence = 2;
    assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Unknown);
    e.sequence = 1; e.facts.last_mut().unwrap().scope.session_id += 1;
    let r = result(&e); assert_eq!(state(&e, HypothesisId::MethodNotExported), State::Unknown);
    assert!(r.trace.excluded.iter().any(|x| x.reasons.contains(&"foreign_scope")));
}
#[test]
fn source_zip_identity_never_authenticates_correlation() {
    let mut e = mismatch(); add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: ReceiverKind::ApplicationObject });
    shape(&mut e, ReceiverKind::ApplicationObject, false); add(&mut e, Predicate::SourceMember, Value::SourcePresence { value: SourcePresence::Present });
    add(&mut e, Predicate::ObjectCorrelation, Value::Correlation { value: Correlation::SameAttested });
    e.facts.last_mut().unwrap().adapter = Adapter::UnverifiedZip;
    assert_eq!(state(&e, HypothesisId::SourceRuntimeMismatch), State::Unknown);
    assert_eq!(result(&e).selected_check.unwrap().check_id, CheckId::ObjectCorrelation);
    e.facts.last_mut().unwrap().adapter = Adapter::Synthetic;
    let r = result(&e); assert_eq!(r.supported, vec![HypothesisId::SourceRuntimeMismatch]);
    assert_eq!(r.assurance, "experimental_synthetic_not_authenticated");
}
#[test]
fn shape_binding_precedes_conflict_grouping() {
    let mut e = receiver(ReceiverKind::Structure); add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: ReceiverKind::Structure });
    shape(&mut e, ReceiverKind::QueryResult, false); shape(&mut e, ReceiverKind::Structure, true);
    assert_eq!(state(&e, HypothesisId::ImmediateMemberAbsent), State::Refuted);
    assert!(result(&e).trace.excluded.iter().any(|x| x.reasons.contains(&"receiver_shape_unbound")));
}
#[test]
fn receiver_kind_conflict_keeps_member_unknown() {
    let mut e = receiver(ReceiverKind::Structure); add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: ReceiverKind::Structure });
    add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: ReceiverKind::QueryResult }); shape(&mut e, ReceiverKind::Structure, false);
    assert_eq!(state(&e, HypothesisId::ImmediateMemberAbsent), State::Unknown);
}
#[test]
fn retained_empty_query_schema_and_existing_structure_key_are_present() {
    for kind in [ReceiverKind::Structure, ReceiverKind::QueryResult, ReceiverKind::QuerySelection] {
        let mut e = receiver(kind); add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: kind }); shape(&mut e, kind, true);
        assert_eq!(result(&e).stop, "all_refuted");
    }
}
#[test]
fn wrong_immediate_receiver_is_foreign_not_evidence() {
    let mut e = receiver(ReceiverKind::Structure); add(&mut e, Predicate::ReceiverKind, Value::ReceiverKind { value: ReceiverKind::Structure });
    shape(&mut e, ReceiverKind::Structure, false);
    if let Target::Receiver { receiver, .. } = &mut e.facts.last_mut().unwrap().target { *receiver += 1; }
    assert_eq!(state(&e, HypothesisId::ImmediateMemberAbsent), State::Unknown);
}
#[test]
fn projection_budget_is_reserved_as_a_whole() {
    let mut e = case(); e.budget.rule_applications_remaining = 21;
    let r = result(&e); assert_eq!(r.stop, "budget_exhausted"); assert_eq!(r.rule_applications_used, 2);
    assert!(r.candidates.is_empty() && r.blocked_checks.is_empty());
}
#[test]
fn cost_only_blockage_is_not_no_useful_check() {
    let mut e = case(); bit(&mut e, Predicate::CompiledCopyPresent, true); e.budget.cost_remaining = 1;
    assert_eq!(result(&e).stop, "budget_exhausted");
}
#[test]
fn consent_is_pending_and_unavailable_is_not_a_fallback() {
    let mut e = case(); e.capabilities[1].state = CapabilityState::ConsentRequired;
    assert_eq!(result(&e).stop, "pending_consent"); assert!(e.attempted_checks.is_empty());
    for c in &mut e.capabilities { c.state = CapabilityState::Unavailable; }
    let r = result(&e); assert_eq!(r.stop, "no_useful_check"); assert!(r.selected_check.is_none());
}
#[test]
fn attempted_checks_never_repeat_and_failure_needs_no_facts() {
    let mut e = case(); e.attempted_checks.push(CheckId::CallFlags); e.budget.observations_remaining = 2; e.budget.cost_remaining = 6;
    let r = result(&e); assert_eq!(r.selected_check.unwrap().check_id, CheckId::CallCopy);
}
#[test]
fn access_revocation_and_cancellation_redact_all_evidence() {
    for revoked in [false, true] {
        let mut e = case(); bit(&mut e, Predicate::Exported, false);
        e.cancelled = !revoked; if revoked { e.access = Access::Revoked; }
        let r = result(&e); assert!(r.hypotheses.is_empty() && r.trace.contributing_ids.is_empty() && r.trace.excluded.is_empty());
        assert!(r.candidates.is_empty() && r.blocked_checks.is_empty()); assert_eq!(r.rule_applications_used, 0);
    }
}
#[test]
fn unsupported_routes_and_profiles_abstain() {
    for target in [Target::Call { site: 1, module: 2, method: 3, module_kind: ModuleKind::Form, route: Route::SameContext },
        Target::Call { site: 1, module: 2, method: 3, module_kind: ModuleKind::Common, route: Route::Dynamic }] {
        let mut e = case(); e.target = target; assert_eq!(result(&e).stop, "unsupported_scope");
    }
    let mut e = case(); e.scope.platform = Platform::Unsupported; assert_eq!(result(&e).stop, "unsupported_scope");
}
#[test]
fn bridge_needs_its_own_server_call_gate() {
    let mut e = case(); if let Target::Call { route, .. } = &mut e.target { *route = Route::ServerBridge; }
    e.facts[0].target = e.target.clone(); bit(&mut e, Predicate::ContextEnabled, true); bit(&mut e, Predicate::CompiledCopyPresent, true); bit(&mut e, Predicate::Exported, true);
    assert_eq!(state(&e, HypothesisId::CallContextUnavailable), State::Unknown);
    bit(&mut e, Predicate::ServerCallEnabled, false); assert_eq!(state(&e, HypothesisId::CallContextUnavailable), State::Supported);
}
#[test]
fn one_step_limit_is_explicit_abstention() {
    let mut e = case(); bit(&mut e, Predicate::Exported, true);
    for predicate in [Predicate::ContextEnabled, Predicate::CompiledCopyPresent] { bit(&mut e, predicate, false); bit(&mut e, predicate, true); }
    assert_eq!(result(&e).stop, "no_useful_check");
}
#[test]
fn fact_order_and_duplicate_values_do_not_change_selection() {
    let mut e = case(); bit(&mut e, Predicate::Exported, true); bit(&mut e, Predicate::Exported, true);
    let first = serde_json::to_value(result(&e)).unwrap(); e.facts.reverse();
    assert_eq!(first, serde_json::to_value(result(&e)).unwrap());
}
#[test]
fn strict_json_and_privacy_reject_generic_errors() {
    let base = serde_json::to_string(&case()).unwrap();
    for input in [base.replacen("\"sequence\":1", "\"sequence\":1.0", 1),
        base.replacen("\"sequence\":1", "\"sequence\":1e0", 1),
        base.replacen("\"sequence\":1", "\"sequence\":-0", 1),
        base.replacen("\"schema_version\":1", "\"schema_version\":1,\"schema_version\":1", 1),
        base.replacen("\"check_id\":null,", "", 1)] {
        assert_eq!(evaluate(input.as_bytes()).unwrap_err(), Error::InvalidEnvelope);
    }
    let mut value = serde_json::to_value(case()).unwrap(); value["secret"] = json!("CANARY_PRIVATE_PATH_TOKEN");
    let err = evaluate(&serde_json::to_vec(&value).unwrap()).unwrap_err();
    assert_eq!(err.json(), b"{\"error\":\"invalid_envelope\"}\n");
    assert_eq!(evaluate(&vec![b' '; INPUT_LIMIT + 1]).unwrap_err(), Error::InputLimit);
    assert_eq!(evaluate(("[".repeat(20) + &"]".repeat(20)).as_bytes()).unwrap_err(), Error::InvalidEnvelope);
}
#[test]
fn irrelevant_predicate_is_rejected_not_silently_repurposed() {
    let mut e = case(); bit(&mut e, Predicate::ReceiverRetained, true);
    assert_eq!(evaluate(&serde_json::to_vec(&e).unwrap()).unwrap_err(), Error::InvalidEnvelope);
}
#[test]
fn partial_flags_do_not_fabricate_unknown_bits() {
    let mut e = case(); bit(&mut e, Predicate::Exported, false);
    assert_eq!(result(&e).supported, vec![HypothesisId::MethodNotExported]);
    assert_eq!(state(&e, HypothesisId::CallContextUnavailable), State::Unknown);
}

fn develop_loop(fixed: bool, copy: bool, context: bool, exported: bool) -> (usize, usize, usize) {
    let mut e = case(); let mut requests = 0; let mut cost = 0; let mut disclosed = 0;
    loop {
        let r = result(&e); e.budget.rule_applications_remaining -= r.rule_applications_used;
        if r.kind == "diagnosis" { return (requests, cost, disclosed); }
        assert_eq!(r.kind, "check_request");
        let c = if fixed { r.candidates.into_iter().min_by_key(|c| c.check_id).unwrap() } else { r.selected_check.unwrap() };
        requests += 1; cost += usize::from(c.cost); disclosed += usize::from(c.max_disclosed_facts);
        e.sequence += 1; e.attempted_checks.push(c.check_id); e.budget.observations_remaining -= 1; e.budget.cost_remaining -= c.cost;
        let before = e.facts.len();
        match c.check_id {
            CheckId::CallCopy => { bit(&mut e, Predicate::CompiledCopyPresent, copy); },
            CheckId::CallFlags => { bit(&mut e, Predicate::ContextEnabled, context); bit(&mut e, Predicate::ServerCallEnabled, false); bit(&mut e, Predicate::Exported, exported); },
            _ => panic!("development catalog only"),
        }
        for f in &mut e.facts[before..] { f.check_id = Some(c.check_id); }
    }
}
#[test]
fn honest_development_selector_tradeoff_counts_cost_and_disclosure() {
    assert_eq!(develop_loop(false, true, true, false), (1, 3, 3));
    assert_eq!(develop_loop(true, true, true, false), (2, 4, 4));
    assert_eq!(develop_loop(false, false, true, true), (2, 4, 4));
    assert_eq!(develop_loop(true, false, true, true), (1, 1, 1));
}
#[test]
fn exact_machine_output_has_no_case_or_target_tokens() {
    let output = serde_json::to_value(result(&case())).unwrap();
    assert_eq!(output.as_object().unwrap().len(), 13);
    assert!(output.get("scope").is_none() && output.get("target").is_none());
    let _: Json = serde_json::from_slice(Error::InvalidEnvelope.json()).unwrap();
}

#[test]
fn scalar_catalog_enums_accept_strings_only() {
    for path in ["/access", "/scope/platform", "/scope/compatibility", "/scope/execution",
        "/target/module_kind", "/target/route", "/capabilities/0/check_id", "/capabilities/0/state",
        "/facts/0/predicate", "/facts/0/state", "/facts/0/adapter", "/facts/0/value/value"] {
        let mut raw = serde_json::to_value(case()).unwrap();
        let scalar = raw.pointer_mut(path).unwrap();
        let label = scalar.as_str().unwrap().to_owned();
        let mut alternative = serde_json::Map::new(); alternative.insert(label, Json::Null);
        *scalar = Json::Object(alternative);
        let error = evaluate(&serde_json::to_vec(&raw).unwrap()).unwrap_err();
        assert_eq!(error, Error::InvalidEnvelope);
        assert_eq!(error.json(), b"{\"error\":\"invalid_envelope\"}\n");
    }
}
#[test]
fn every_record_requires_object_shape_not_positional_array() {
    let paths_and_fields: &[(&str, &[&str])] = &[
        ("", &["schema_version", "rule_version", "catalog_version", "scope", "target", "sequence",
            "access", "cancelled", "budget", "attempted_checks", "capabilities", "facts"]),
        ("/scope", &["case_id", "snapshot_id", "revision_id", "session_id", "context_id", "platform", "compatibility", "execution"]),
        ("/budget", &["observations_remaining", "cost_remaining", "rule_applications_remaining"]),
        ("/capabilities/0", &["check_id", "state"]),
        ("/target", &["kind", "site", "module", "method", "module_kind", "route"]),
        ("/facts/0", &["id", "scope", "target", "predicate", "value", "state", "adapter", "adapter_version",
            "input_id", "check_id", "sequence", "valid_until", "supersedes"]),
        ("/facts/0/scope", &["case_id", "snapshot_id", "revision_id", "session_id", "context_id", "platform", "compatibility", "execution"]),
        ("/facts/0/target", &["kind", "site", "module", "method", "module_kind", "route"]),
        ("/facts/0/value", &["kind", "value"]),
    ];
    for (path, fields) in paths_and_fields {
        let mut raw = serde_json::to_value(case()).unwrap();
        let record = raw.pointer_mut(path).unwrap();
        let positional = fields.iter().map(|field| record[*field].clone()).collect();
        *record = Json::Array(positional);
        assert_eq!(evaluate(&serde_json::to_vec(&raw).unwrap()).unwrap_err(), Error::InvalidEnvelope);
    }
}
