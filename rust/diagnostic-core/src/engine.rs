use crate::{catalog, model::*};
use std::collections::{BTreeMap, BTreeSet};

type Reasons = BTreeSet<&'static str>;
#[derive(Clone)]
struct Witness { id: u16, value: Value, conflicting: bool }
#[derive(Clone, Default)]
struct Evidence {
    groups: BTreeMap<Predicate, Vec<Witness>>,
    excluded: BTreeMap<u16, Reasons>,
    problems: BTreeMap<Predicate, Reasons>,
}
#[derive(Clone, Default)]
struct Slot { value: Option<Value>, ids: Vec<u16>, conflicting: bool }
#[derive(Default)]
struct View {
    slots: BTreeMap<Predicate, Slot>,
    excluded: BTreeMap<u16, Reasons>,
    problems: BTreeMap<Predicate, Reasons>,
}
impl View {
    fn value(&self, p: Predicate) -> Option<&Value> { self.slots.get(&p).and_then(|s| s.value.as_ref()) }
    fn boolean(&self, p: Predicate) -> Option<bool> { match self.value(p) { Some(Value::Bool { value }) => Some(*value), _ => None } }
    fn kind(&self) -> Option<ReceiverKind> { match self.value(Predicate::ReceiverKind) { Some(Value::ReceiverKind { value }) => Some(*value), _ => None } }
    fn member(&self) -> Option<bool> { match self.value(Predicate::MemberPresent) { Some(Value::Shape { present, .. }) => Some(*present), _ => None } }
    fn conflict(&self, p: Predicate) -> bool { self.slots.get(&p).is_some_and(|s| s.conflicting) }
    fn resolved(&self, p: Predicate) -> bool { self.value(p).is_some_and(Value::resolved) }
    fn ids(&self, p: Predicate) -> Vec<u16> { self.slots.get(&p).map(|s| s.ids.clone()).unwrap_or_default() }
}
fn add(map: &mut BTreeMap<u16, Reasons>, id: u16, reason: &'static str) {
    if id != 0 { map.entry(id).or_default().insert(reason); }
}
fn problem_for(reason: &str) -> Option<&'static str> {
    match reason {
        "stale" => Some("stale_evidence"), "revoked" => Some("revoked_evidence"),
        "unavailable" => Some("unavailable_evidence"), "untrusted" => Some("untrusted_evidence"),
        "conflicting" => Some("conflicting_evidence"), "receiver_shape_unbound" => Some("unbound_shape"), _ => None,
    }
}
fn gather(e: &Envelope) -> Evidence {
    let mut evidence = Evidence::default();
    let superseded: BTreeSet<u16> = e.facts.iter().flat_map(|f| f.supersedes.iter().copied()).collect();
    for f in &e.facts {
        let mut reasons = Reasons::new();
        if f.scope != e.scope { reasons.insert("foreign_scope"); }
        if f.target != e.target { reasons.insert("foreign_target"); }
        if f.adapter != Adapter::Synthetic { reasons.insert("untrusted"); }
        if superseded.contains(&f.id) { reasons.insert("superseded"); }
        if f.sequence > e.sequence { reasons.insert("future_observation"); }
        if f.valid_until < e.sequence || f.state == FactState::Stale { reasons.insert("stale"); }
        match f.state {
            FactState::Revoked => { reasons.insert("revoked"); },
            FactState::Unavailable => { reasons.insert("unavailable"); }, _ => {},
        }
        if reasons.is_empty() {
            evidence.groups.entry(f.predicate).or_default().push(Witness {
                id: f.id, value: f.value.clone(), conflicting: f.state == FactState::Conflicting,
            });
        }
        if f.state == FactState::Conflicting { reasons.insert("conflicting"); }
        if f.scope == e.scope && f.target == e.target {
            for reason in &reasons {
                if let Some(problem) = problem_for(reason) { evidence.problems.entry(f.predicate).or_default().insert(problem); }
            }
        }
        if !reasons.is_empty() { evidence.excluded.insert(f.id, reasons); }
    }
    evidence
}
fn slot(records: &[Witness], p: Predicate, view: &mut View) -> Slot {
    if records.is_empty() { return Slot::default(); }
    let conflicting = records.iter().any(|r| r.conflicting || r.value != records[0].value);
    if conflicting {
        for record in records { add(&mut view.excluded, record.id, "conflicting"); }
        view.problems.entry(p).or_default().insert("conflicting_evidence");
        Slot { conflicting: true, ..Slot::default() }
    } else {
        let ids = records.iter().map(|r| r.id).filter(|id| *id != 0).collect::<BTreeSet<_>>().into_iter().collect();
        Slot { value: Some(records[0].value.clone()), ids, conflicting: false }
    }
}
fn normalize(evidence: &Evidence) -> View {
    let mut view = View { excluded: evidence.excluded.clone(), problems: evidence.problems.clone(), ..View::default() };
    for (p, records) in &evidence.groups {
        if *p != Predicate::MemberPresent {
            let s = slot(records, *p, &mut view); view.slots.insert(*p, s);
        }
    }
    if let Some(records) = evidence.groups.get(&Predicate::MemberPresent) {
        let mut bound = Vec::new();
        for record in records {
            if matches!(&record.value, Value::Shape { receiver_kind, .. } if Some(*receiver_kind) == view.kind()) {
                bound.push(record.clone());
            } else {
                add(&mut view.excluded, record.id, "receiver_shape_unbound");
                view.problems.entry(Predicate::MemberPresent).or_default().insert("unbound_shape");
            }
        }
        let s = slot(&bound, Predicate::MemberPresent, &mut view); view.slots.insert(Predicate::MemberPresent, s);
    }
    view
}
fn supported_scope(e: &Envelope) -> bool {
    if e.scope.platform != Platform::Synthetic || e.scope.compatibility != Compatibility::Synthetic
        || e.scope.execution == Execution::Unknown { return false; }
    match e.target {
        Target::Call { module_kind: ModuleKind::Common, route: Route::SameContext, .. } => true,
        Target::Call { module_kind: ModuleKind::Common, route: Route::ServerBridge, .. } => e.scope.execution == Execution::ThinClient,
        Target::Call { .. } => false,
        _ => true,
    }
}
fn anchor(target: &Target) -> Predicate {
    if matches!(target, Target::Call { .. }) { Predicate::CallEdge } else { Predicate::ReceiverRetained }
}
fn anchor_present(target: &Target, view: &View) -> bool {
    match target {
        Target::Call { .. } => matches!(view.value(Predicate::CallEdge), Some(Value::Edge { value: Edge::StaticExternalResolved })),
        _ => view.boolean(Predicate::ReceiverRetained) == Some(true),
    }
}
fn blank_hypotheses(target: &Target, reason: &'static str) -> Vec<Hypothesis> {
    catalog::hypotheses(target).into_iter().map(|id| Hypothesis { id, state: State::Unknown, rule_id: catalog::rule(id),
        evidence_ids: Vec::new(), unknown_reasons: vec![reason], missing_predicates: Vec::new() }).collect()
}
fn base() -> DiagnosticResult {
    DiagnosticResult { schema_version: 1, rule_version: 1, catalog_version: 1,
        assurance: "experimental_synthetic_not_authenticated", kind: "insufficient_data", stop: "no_useful_check",
        hypotheses: Vec::new(), supported: Vec::new(), trace: Trace::default(), candidates: Vec::new(),
        selected_check: None, blocked_checks: Vec::new(), rule_applications_used: 0 }
}
fn state(id: HypothesisId, target: &Target, view: &View) -> State {
    use HypothesisId as H; use Predicate as P;
    if catalog::dependencies(id, target).iter().any(|p| view.conflict(*p)) { return State::Unknown; }
    // Anchors are checked before all actual or projected assessments.
    match id {
        H::CallContextUnavailable => {
            let mut gates = vec![view.boolean(P::ContextEnabled), view.boolean(P::CompiledCopyPresent)];
            if matches!(target, Target::Call { route: Route::ServerBridge, .. }) { gates.push(view.boolean(P::ServerCallEnabled)); }
            if gates.contains(&Some(false)) { State::Supported }
            else if gates.iter().all(|g| *g == Some(true)) { State::Refuted } else { State::Unknown }
        },
        H::MethodNotExported => match view.boolean(P::Exported) { Some(false) => State::Supported, Some(true) => State::Refuted, None => State::Unknown },
        H::ReceiverKindMismatch => match (target, view.kind()) {
            (Target::Receiver { expected_kind, .. }, Some(actual)) => if actual == *expected_kind { State::Refuted } else { State::Supported }, _ => State::Unknown,
        },
        H::ImmediateMemberAbsent => match (view.kind(), view.member()) {
            (Some(_), Some(false)) => State::Supported, (Some(_), Some(true)) => State::Refuted, _ => State::Unknown,
        },
        H::SourceRuntimeMismatch => {
            let source = view.value(P::SourceMember);
            let correlation = view.value(P::ObjectCorrelation);
            if view.kind().is_some_and(|k| k != ReceiverKind::ApplicationObject)
                || matches!(source, Some(Value::SourcePresence { value: SourcePresence::AbsentComplete }))
                || view.member() == Some(true)
                || matches!(correlation, Some(Value::Correlation { value: Correlation::DifferentAttested })) { return State::Refuted; }
            if view.kind() == Some(ReceiverKind::ApplicationObject) && view.member() == Some(false)
                && matches!(source, Some(Value::SourcePresence { value: SourcePresence::Present }))
                && matches!(correlation, Some(Value::Correlation { value: Correlation::SameAttested })) { State::Supported } else { State::Unknown }
        },
    }
}
fn assess(target: &Target, view: &View) -> Vec<Hypothesis> {
    catalog::hypotheses(target).into_iter().map(|id| {
        let state = state(id, target, view);
        let deps = catalog::dependencies(id, target);
        let evidence_ids = deps.iter().flat_map(|p| view.ids(*p)).collect::<BTreeSet<_>>().into_iter().collect();
        let mut missing_predicates = Vec::new(); let mut reasons = Reasons::new();
        if state == State::Unknown {
            for p in &deps {
                if !view.resolved(*p) {
                    missing_predicates.push(*p);
                    if view.conflict(*p) { reasons.insert("conflicting_evidence"); }
                    if view.value(*p).is_some_and(|v| !v.resolved()) { reasons.insert("unresolved_witness"); }
                    if let Some(problems) = view.problems.get(p) { reasons.extend(problems); }
                    if !view.conflict(*p) && view.value(*p).is_none() && !view.problems.get(p).is_some_and(|x| !x.is_empty()) {
                        reasons.insert("missing_witness");
                    }
                }
            }
            if reasons.is_empty() { reasons.insert("missing_witness"); }
        }
        Hypothesis { id, state, rule_id: catalog::rule(id), evidence_ids,
            unknown_reasons: reasons.into_iter().collect(), missing_predicates }
    }).collect()
}
fn compatible(outcome: &Outcome, view: &View) -> bool {
    outcome.facts.iter().all(|f| match view.value(f.predicate) {
        Some(value) if value.resolved() => *value == f.value, _ => true,
    })
}
fn project(evidence: &Evidence, outcome: &Outcome) -> View {
    let mut hypothetical = evidence.clone();
    for f in &outcome.facts {
        hypothetical.groups.insert(f.predicate, vec![Witness { id: 0, value: f.value.clone(), conflicting: false }]);
        hypothetical.problems.remove(&f.predicate);
    }
    normalize(&hypothetical)
}
fn structural(e: &Envelope, view: &View, check: CheckId) -> Reasons {
    let mut reasons = Reasons::new();
    let matching_target = match check {
        CheckId::CallCopy | CheckId::CallFlags => matches!(e.target, Target::Call { .. }),
        CheckId::ReceiverKind | CheckId::ReceiverShape => !matches!(e.target, Target::Call { .. }),
        CheckId::SourcePresence | CheckId::ObjectCorrelation => matches!(e.target, Target::Mismatch { .. }),
    };
    if !matching_target { reasons.insert("unsupported_target"); }
    if !anchor_present(&e.target, view) { reasons.insert("missing_anchor"); }
    if check == CheckId::ReceiverShape && view.kind().and_then(catalog::witness).is_none() { reasons.insert("missing_prerequisite"); }
    if e.attempted_checks.contains(&check) { reasons.insert("already_attempted"); }
    if !e.capabilities.iter().any(|c| c.check_id == check && c.state != CapabilityState::Unavailable) { reasons.insert("unavailable_capability"); }
    reasons
}
fn candidate(e: &Envelope, view: &View, evidence: &Evidence, current: &[Hypothesis], check: CheckId, outcomes: Vec<Outcome>) -> Candidate {
    let projections: Vec<Vec<Hypothesis>> = outcomes.iter().map(|o| assess(&e.target, &project(evidence, o))).collect();
    let affected: Vec<_> = current.iter().enumerate().filter(|(i, h)| projections.iter().any(|p| p[*i].state != h.state))
        .map(|(_, h)| h.id).collect();
    let resolve_score = current.iter().enumerate().filter(|(i, h)| h.state == State::Unknown
        && projections.iter().any(|p| p[*i].state != State::Unknown)).count() as u8;
    let mut pair_score = 0;
    for a in 0..current.len() {
        for b in a + 1..current.len() {
            if current[a].state != State::Refuted && current[b].state != State::Refuted
                && projections.iter().any(|p| p[a].state != p[b].state) { pair_score += 1; }
        }
    }
    let mut prerequisite_fact_ids = view.ids(anchor(&e.target));
    if check == CheckId::ReceiverShape { prerequisite_fact_ids.extend(view.ids(Predicate::ReceiverKind)); }
    prerequisite_fact_ids.sort(); prerequisite_fact_ids.dedup();
    let mut missing_predicates: Vec<_> = catalog::outputs(check).iter().copied().filter(|p| !view.resolved(*p)).collect();
    missing_predicates.sort();
    let consent = if e.capabilities.iter().any(|c| c.check_id == check && c.state == CapabilityState::ConsentRequired) { "pending_consent" } else { "ready" };
    Candidate { check_id: check, pair_score, resolve_score, observation_charge: 1,
        max_disclosed_facts: catalog::cost(check), cost: catalog::cost(check), consent,
        prerequisite_fact_ids, affected_hypotheses: affected, missing_predicates, outcomes }
}
pub(crate) fn evaluate(e: &Envelope) -> DiagnosticResult {
    let mut result = base();
    if e.access == Access::Revoked { result.stop = "access_revoked"; return result; }
    if e.cancelled { result.stop = "cancelled"; return result; }
    if !supported_scope(e) {
        result.stop = "unsupported_scope"; result.hypotheses = blank_hypotheses(&e.target, result.stop); return result;
    }
    let evidence = gather(e); let view = normalize(&evidence);
    if !anchor_present(&e.target, &view) {
        result.stop = if view.conflict(anchor(&e.target)) { "conflicting_anchor" } else { "missing_anchor" };
        result.hypotheses = blank_hypotheses(&e.target, result.stop); return result;
    }
    let count = catalog::hypotheses(&e.target).len() as u16;
    if e.budget.rule_applications_remaining < count {
        result.stop = "budget_exhausted"; result.hypotheses = blank_hypotheses(&e.target, result.stop); return result;
    }
    result.hypotheses = assess(&e.target, &view); result.rule_applications_used = count;
    result.supported = result.hypotheses.iter().filter(|h| h.state == State::Supported).map(|h| h.id).collect();
    result.trace = Trace {
        contributing_ids: result.hypotheses.iter().flat_map(|h| h.evidence_ids.iter().copied()).collect::<BTreeSet<_>>().into_iter().collect(),
        excluded: view.excluded.iter().map(|(fact_id, reasons)| Excluded { fact_id: *fact_id, reasons: reasons.iter().copied().collect() }).collect(),
    };
    if !result.supported.is_empty() { result.kind = "diagnosis"; result.stop = "bounded_finding"; return result; }
    if result.hypotheses.iter().all(|h| h.state == State::Refuted) { result.stop = "all_refuted"; return result; }
    let mut pending = Vec::new(); let mut blocked = BTreeMap::new();
    for check in catalog::CHECKS {
        let reasons = structural(e, &view, check);
        if reasons.is_empty() {
            let outcomes: Vec<_> = catalog::outcomes(check, view.kind()).into_iter().filter(|o| compatible(o, &view)).collect();
            pending.push((check, outcomes));
        } else { blocked.insert(check, reasons); }
    }
    let projection_charge = count * pending.iter().map(|(_, outcomes)| outcomes.len() as u16).sum::<u16>();
    if projection_charge > e.budget.rule_applications_remaining - count { result.stop = "budget_exhausted"; return result; }
    result.rule_applications_used += projection_charge;
    let mut budget_blocked = false;
    for (check, outcomes) in pending {
        let c = candidate(e, &view, &evidence, &result.hypotheses, check, outcomes);
        let mut reasons = Reasons::new();
        if c.pair_score == 0 && c.resolve_score == 0 { reasons.insert("no_status_change"); }
        if e.budget.observations_remaining == 0 { reasons.insert("observation_budget"); }
        if e.budget.cost_remaining < c.cost { reasons.insert("cost_budget"); }
        if (c.pair_score > 0 || c.resolve_score > 0) && !reasons.is_empty() { budget_blocked = true; }
        if reasons.is_empty() { result.candidates.push(c); } else { blocked.insert(check, reasons); }
    }
    result.candidates.sort_by(|a, b| b.pair_score.cmp(&a.pair_score).then(b.resolve_score.cmp(&a.resolve_score))
        .then(a.observation_charge.cmp(&b.observation_charge)).then(a.cost.cmp(&b.cost)).then(a.check_id.cmp(&b.check_id)));
    result.blocked_checks = blocked.into_iter().map(|(check_id, reasons)| BlockedCheck { check_id, reasons: reasons.into_iter().collect() }).collect();
    if let Some(selected) = result.candidates.first().cloned() {
        result.kind = "check_request"; result.stop = if selected.consent == "pending_consent" { "pending_consent" } else { "awaiting_observation" };
        result.selected_check = Some(selected);
    } else if budget_blocked { result.stop = "budget_exhausted"; }
    result
}
