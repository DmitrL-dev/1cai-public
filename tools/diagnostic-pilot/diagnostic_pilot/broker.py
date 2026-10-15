"""Case-owned evidence ledger. Legal probes do not depend on Rust scoring."""
import copy
from .contracts import CHECKS, WITNESSES, Invalid, encoded, enum, exact, fact_value, require, scope, validate_envelope


def active(envelope):
    eligible = [f for f in envelope['facts'] if f['scope'] == envelope['scope'] and f['target'] == envelope['target']
                and f['adapter'] == 'synthetic_v1' and f['sequence'] <= envelope['sequence']]
    suppressed = {ident for f in eligible for ident in f['supersedes']}
    groups = {}
    for f in eligible:
        if f['id'] not in suppressed and envelope['sequence'] <= f['valid_until'] and f['state'] in {'observed', 'conflicting'}:
            groups.setdefault(f['predicate'], []).append(f)
    result = {}
    for predicate, facts in groups.items():
        if all(f['state'] == 'observed' for f in facts) and len({encoded(f['value']) for f in facts}) == 1:
            result[predicate] = (facts[0]['value'], [f['id'] for f in facts])
    return result


def supported_scope(envelope):
    s, t = envelope['scope'], envelope['target']
    return s['platform'] == 'synthetic_8_3_27' and s['compatibility'] == 'synthetic_v1' and s['execution'] != 'unknown' and (
        t['kind'] != 'call' or t['module_kind'] == 'common' and (t['route'] == 'same_context' or t['route'] == 'server_bridge' and s['execution'] == 'thin_client'))


def eligible_checks(envelope):
    """Admission only: no status projection, pair score or no_status_change filter."""
    facts = active(envelope); kind = envelope['target']['kind']
    if envelope['access'] != 'usable' or envelope['cancelled'] or not supported_scope(envelope):
        return []
    anchor = facts.get('call_edge' if kind == 'call' else 'receiver_retained')
    if anchor is None or anchor[0]['value'] != ('static_external_resolved' if kind == 'call' else True):
        return []
    capabilities = {c['check_id']: c['state'] for c in envelope['capabilities']}
    result = []
    for check, (family, cost, outputs) in CHECKS.items():
        if family == 'call' and kind != 'call' or family == 'receiver' and kind == 'call' or family == 'mismatch' and kind != 'mismatch':
            continue
        state = capabilities.get(check, 'unavailable')
        if state == 'unavailable' or check in envelope['attempted_checks']:
            continue
        if check == 'c11_receiver_shape' and facts.get('receiver_kind', ({},))[0].get('value') not in WITNESSES:
            continue
        if envelope['budget']['observations_remaining'] < 1 or envelope['budget']['cost_remaining'] < cost:
            continue
        result.append({'check_id': check, 'cost': cost, 'outputs': list(outputs), 'consent': state})
    return result


def validate_outcome(check, outcome, envelope):
    exact(outcome, 'status facts'); enum(outcome['status'], {'observed', 'unavailable', 'timeout'})
    require(type(outcome['facts']) is list, 'invalid_outcome')
    if outcome['status'] != 'observed':
        require(not outcome['facts'], 'failed_outcome_disclosure'); return
    require(len(outcome['facts']) == len(CHECKS[check][2]), 'incomplete_bundle')
    seen = set(); current = active(envelope)
    for item in outcome['facts']:
        exact(item, 'predicate value'); predicate = item['predicate']
        require(predicate in CHECKS[check][2] and predicate not in seen, 'invalid_bundle')
        seen.add(predicate); fact_value(predicate, item['value'])
        require(predicate not in current or current[predicate][0] == item['value'], 'incompatible_outcome')
        if predicate == 'member_present':
            require(current.get('receiver_kind', ({},))[0].get('value') == item['value']['receiver_kind'], 'foreign_receiver_shape')


class Broker:
    def __init__(self, case):
        self._envelope = validate_envelope(case['initial'])
        require(not self._envelope['attempted_checks'] and all(f['check_id'] is None for f in self._envelope['facts']), 'initial_ledger_required')
        self._outcomes = copy.deepcopy(case['outcomes'])
        self._attempts = 0
        self._initial_observations = self._envelope['budget']['observations_remaining']
        self._initial_cost = self._envelope['budget']['cost_remaining']
        self._cost = self._disclosure = 0
        self._retirements = []
        self._used_ids = {f['id'] for f in self._envelope['facts']}
        self._next_id = max(self._used_ids or {0}) + 1

    def view(self):
        return {'envelope': copy.deepcopy(self._envelope), 'checks': eligible_checks(self._envelope)}

    def charge_reasoning(self, used):
        require(type(used) is int and 0 <= used <= self._envelope['budget']['rule_applications_remaining'], 'rule_budget')
        self._envelope['budget']['rule_applications_remaining'] -= used

    def request(self, check):
        enum(check, CHECKS)
        legal = {c['check_id']: c for c in eligible_checks(self._envelope)}
        require(check in legal, 'ineligible_check')
        require(legal[check]['consent'] == 'ready', 'consent_required')
        require(check in self._outcomes, 'missing_outcome')
        # Admission and full outcome validation precede any ledger mutation.
        outcome = copy.deepcopy(self._outcomes[check])
        validate_outcome(check, outcome, self._envelope)
        attempts, cost = self._attempts + 1, self._cost + CHECKS[check][1]
        require(attempts <= self._initial_observations and cost <= self._initial_cost, 'cumulative_budget')
        candidate = copy.deepcopy(self._envelope)
        next_id = self._next_id
        candidate['attempted_checks'].append(check)
        candidate['budget']['observations_remaining'] -= 1
        candidate['budget']['cost_remaining'] -= CHECKS[check][1]
        candidate['sequence'] += 1
        if outcome['status'] == 'observed':
            for item in outcome['facts']:
                e = candidate
                predecessors = [f['id'] for f in e['facts'] if f['scope'] == e['scope'] and f['target'] == e['target']
                                and f['adapter'] == 'synthetic_v1' and f['predicate'] == item['predicate']]
                ident = next_id; next_id += 1
                e['facts'].append({'id': ident, 'scope': copy.deepcopy(e['scope']), 'target': copy.deepcopy(e['target']),
                    'predicate': item['predicate'], 'value': item['value'], 'state': 'observed',
                    'adapter': 'synthetic_v1', 'adapter_version': 1, 'input_id': ident, 'check_id': check,
                    'sequence': e['sequence'], 'valid_until': 65535, 'supersedes': predecessors})
        validate_envelope(candidate)
        self._envelope = candidate
        self._attempts, self._cost = attempts, cost
        self._disclosure += len(outcome['facts'])
        self._used_ids.update(f['id'] for f in candidate['facts'])
        self._next_id = next_id
        return {'check_id': check, 'status': outcome['status'], 'disclosed_facts': len(outcome['facts']),
                'cost': CHECKS[check][1], 'attempts_total': self._attempts, 'cost_total': self._cost}

    def advance_scope(self, replacement_scope, fresh_facts):
        """Trusted fixture/host event, never an action offered to a policy.

        Retired facts remain in bounded history with original provenance. They
        are removed from the wire permanently, including on scope A->B->A.
        No cumulative budget is refunded when a check becomes eligible again.
        """
        scope(replacement_scope)
        require(replacement_scope['case_id'] == self._envelope['scope']['case_id'], 'foreign_case')
        require(replacement_scope != self._envelope['scope'], 'unchanged_scope')
        require(len(self._retirements) < 8, 'scope_transition_limit')
        candidate = copy.deepcopy(self._envelope)
        candidate['scope'] = copy.deepcopy(replacement_scope)
        candidate['sequence'] += 1
        candidate['attempted_checks'] = []
        require(type(fresh_facts) is list, 'invalid_facts')
        require(all(type(f) is dict and type(f.get('id')) is int and f['id'] not in self._used_ids for f in fresh_facts), 'reused_fact_id')
        require(all(f.get('scope') == replacement_scope and f.get('target') == candidate['target']
                    and f.get('sequence') == candidate['sequence'] and f.get('check_id') is None for f in fresh_facts), 'fresh_scope_witness_required')
        candidate['facts'] = copy.deepcopy(fresh_facts)
        admitted = validate_envelope(candidate)
        self._retirements.append({'reason': 'scope_changed', 'scope': copy.deepcopy(self._envelope['scope']),
                                  'facts': copy.deepcopy(self._envelope['facts'])})
        self._envelope = admitted
        self._used_ids.update(f['id'] for f in fresh_facts)
        self._next_id = max(self._used_ids or {0}) + 1

    def history(self):
        return copy.deepcopy(self._retirements)

    def totals(self):
        return {'attempts': self._attempts, 'cost': self._cost, 'disclosed_facts': self._disclosure}
