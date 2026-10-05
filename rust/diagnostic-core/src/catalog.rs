//! Closed catalog; these outcomes are possibilities, never actual observations.
use crate::model::*;

pub(crate) const CHECKS: [CheckId; 6] = [CheckId::CallCopy, CheckId::CallFlags, CheckId::ReceiverKind,
    CheckId::ReceiverShape, CheckId::SourcePresence, CheckId::ObjectCorrelation];
pub(crate) fn cost(check: CheckId) -> u8 { if check == CheckId::CallFlags { 3 } else { 1 } }
pub(crate) fn outputs(check: CheckId) -> &'static [Predicate] {
    use Predicate as P;
    match check {
        CheckId::CallCopy => &[P::CompiledCopyPresent],
        CheckId::CallFlags => &[P::ContextEnabled, P::ServerCallEnabled, P::Exported],
        CheckId::ReceiverKind => &[P::ReceiverKind], CheckId::ReceiverShape => &[P::MemberPresent],
        CheckId::SourcePresence => &[P::SourceMember], CheckId::ObjectCorrelation => &[P::ObjectCorrelation],
    }
}
pub(crate) fn witness(kind: ReceiverKind) -> Option<ShapeWitness> {
    match kind {
        ReceiverKind::Structure => Some(ShapeWitness::KeyPresence),
        ReceiverKind::QueryResult | ReceiverKind::QuerySelection => Some(ShapeWitness::QuerySchema),
        ReceiverKind::ApplicationObject => Some(ShapeWitness::SessionMetadata), ReceiverKind::Other => None,
    }
}
pub(crate) fn hypotheses(target: &Target) -> Vec<HypothesisId> {
    use HypothesisId as H;
    match target {
        Target::Call { .. } => vec![H::CallContextUnavailable, H::MethodNotExported],
        Target::Receiver { .. } => vec![H::ImmediateMemberAbsent, H::ReceiverKindMismatch],
        Target::Mismatch { .. } => vec![H::SourceRuntimeMismatch],
    }
}
pub(crate) fn rule(id: HypothesisId) -> &'static str {
    use HypothesisId as H;
    match id {
        H::CallContextUnavailable => "r_call_context_v1", H::MethodNotExported => "r_call_export_v1",
        H::ImmediateMemberAbsent => "r_receiver_member_v1", H::ReceiverKindMismatch => "r_receiver_kind_v1",
        H::SourceRuntimeMismatch => "r_mismatch_v1",
    }
}
pub(crate) fn dependencies(id: HypothesisId, target: &Target) -> Vec<Predicate> {
    use HypothesisId as H; use Predicate as P;
    let mut deps = match id {
        H::CallContextUnavailable => {
            let mut d = vec![P::CallEdge, P::ContextEnabled, P::CompiledCopyPresent];
            if matches!(target, Target::Call { route: Route::ServerBridge, .. }) { d.push(P::ServerCallEnabled); }
            d
        },
        H::MethodNotExported => vec![P::CallEdge, P::Exported],
        H::ImmediateMemberAbsent => vec![P::ReceiverRetained, P::ReceiverKind, P::MemberPresent],
        H::ReceiverKindMismatch => vec![P::ReceiverRetained, P::ReceiverKind],
        H::SourceRuntimeMismatch => vec![P::ReceiverRetained, P::ReceiverKind, P::MemberPresent, P::SourceMember, P::ObjectCorrelation],
    };
    deps.sort(); deps
}
fn single(outcome_id: u8, predicate: Predicate, value: Value) -> Outcome {
    Outcome { outcome_id, facts: vec![OutcomeFact { predicate, value }] }
}
pub(crate) fn outcomes(check: CheckId, kind: Option<ReceiverKind>) -> Vec<Outcome> {
    use Predicate as P;
    match check {
        CheckId::CallCopy => (0..2).map(|id| single(id, P::CompiledCopyPresent, Value::Bool { value: id == 1 })).collect(),
        CheckId::CallFlags => (0..8).map(|id| Outcome { outcome_id: id, facts: vec![
            OutcomeFact { predicate: P::ContextEnabled, value: Value::Bool { value: id & 4 != 0 } },
            OutcomeFact { predicate: P::Exported, value: Value::Bool { value: id & 1 != 0 } },
            OutcomeFact { predicate: P::ServerCallEnabled, value: Value::Bool { value: id & 2 != 0 } },
        ] }).collect(),
        CheckId::ReceiverKind => [ReceiverKind::Structure, ReceiverKind::QueryResult, ReceiverKind::QuerySelection,
            ReceiverKind::ApplicationObject, ReceiverKind::Other].into_iter().enumerate()
            .map(|(id, value)| single(id as u8, P::ReceiverKind, Value::ReceiverKind { value })).collect(),
        CheckId::ReceiverShape => match kind.and_then(|k| witness(k).map(|w| (k, w))) {
            Some((receiver_kind, witness)) => (0..2).map(|id| single(id, P::MemberPresent,
                Value::Shape { present: id == 1, receiver_kind, witness })).collect(),
            None => Vec::new(),
        },
        CheckId::SourcePresence => vec![single(0, P::SourceMember, Value::SourcePresence { value: SourcePresence::Present }),
            single(1, P::SourceMember, Value::SourcePresence { value: SourcePresence::AbsentComplete })],
        CheckId::ObjectCorrelation => [Correlation::SameAttested, Correlation::DifferentAttested, Correlation::Unverified]
            .into_iter().enumerate().map(|(id, value)| single(id as u8, P::ObjectCorrelation, Value::Correlation { value })).collect(),
    }
}
