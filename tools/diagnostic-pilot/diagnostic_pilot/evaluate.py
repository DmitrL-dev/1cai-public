"""Independent rule/record evaluator; never imports the Rust policy or broker."""
import copy
import hashlib
from .contracts import CHECKS, WITNESSES, action, encoded, require, validate_envelope


def observations(envelope):
    """Derive evidence from the wire itself, independent of policy states."""
    current = [f for f in envelope['facts'] if f['scope'] == envelope['scope'] and f['target'] == envelope['target']
               and f['adapter'] == 'synthetic_v1' and f['sequence'] <= envelope['sequence']]
    superseded = set()
    for successor in current:
        superseded.update(successor['supersedes'])
    values, conflicts, ids = {}, set(), {}
    for fact in current:
        if fact['id'] in superseded or fact['valid_until'] < envelope['sequence']:
            continue
        key = fact['predicate']
        if fact['state'] == 'conflicting':
            conflicts.add(key)
        elif fact['state'] == 'observed':
            if key in values and values[key] != fact['value']:
                conflicts.add(key)
            values[key] = fact['value']; ids.setdefault(key, []).append(fact['id'])
    for key in conflicts:
        values.pop(key, None); ids.pop(key, None)
    if 'member_present' in values and values['member_present']['receiver_kind'] != values.get('receiver_kind', {}).get('value'):
        values.pop('member_present'); ids.pop('member_present', None)
    return values, conflicts, ids


def findings(envelope):
    """Five published finite rules; no hidden labels are inputs here."""
    values, conflicts, ids = observations(envelope)
    s, t = envelope['scope'], envelope['target']
    if envelope['access'] != 'usable' or envelope['cancelled'] or s['platform'] != 'synthetic_8_3_27' or s['compatibility'] != 'synthetic_v1' or s['execution'] == 'unknown':
        return {}, ids
    kind = t['kind']
    if kind == 'call' and (t['module_kind'] != 'common' or t['route'] == 'dynamic' or t['route'] == 'server_bridge' and s['execution'] != 'thin_client'):
        return {}, ids
    anchor = 'call_edge' if kind == 'call' else 'receiver_retained'
    if values.get(anchor, {}).get('value') != ('static_external_resolved' if kind == 'call' else True):
        return {}, ids
    def value(key):
        v = values.get(key, {})
        return v.get('present') if key == 'member_present' else v.get('value')
    states = {}
    def record(name, dependencies, supported, refuted):
        states[name] = 'unknown' if conflicts & set(dependencies) else 'supported' if supported else 'refuted' if refuted else 'unknown'
    if kind == 'call':
        deps = [anchor, 'context_enabled', 'compiled_copy_present']
        if t['route'] == 'server_bridge':
            deps.append('server_call_enabled')
        gates = [value(p) for p in deps if p != anchor]
        record('call_context_unavailable', deps, False in gates, all(v is True for v in gates))
        record('method_not_exported', [anchor, 'exported'], value('exported') is False, value('exported') is True)
    elif kind == 'receiver':
        record('receiver_kind_mismatch', [anchor, 'receiver_kind'], value('receiver_kind') is not None and value('receiver_kind') != t['expected_kind'], value('receiver_kind') == t['expected_kind'])
        record('immediate_member_absent', [anchor, 'receiver_kind', 'member_present'], value('member_present') is False, value('member_present') is True)
    else:
        deps = [anchor, 'receiver_kind', 'member_present', 'source_member', 'object_correlation']
        good = value('receiver_kind') == 'application_object' and value('member_present') is False and value('source_member') == 'present' and value('object_correlation') == 'same_attested'
        negative = value('receiver_kind') is not None and value('receiver_kind') != 'application_object' or value('member_present') is True or value('source_member') == 'absent_complete' or value('object_correlation') == 'different_attested'
        record('source_runtime_mismatch', deps, good, negative)
    return states, ids


def audit(case, episode):
    """Replay the ledger independently. Corrupt/ineligible reveals fail closed."""
    require(episode['case_id'] == case['id'] and type(episode['events']) is list and len(episode['events']) <= 4, 'incomplete_schedule')
    if episode['policy'] == 'model_one_shot':
        require(len(episode['events']) == 1 and action(episode['events'][0]['action'])['kind'] != 'check', 'one_shot_terminal_required')
    expected = copy.deepcopy(case['initial'])
    attempts = cost = disclosed = 0
    terminal = None
    for index, event in enumerate(episode['events']):
        require(terminal is None and event['before'] == expected, 'record_discontinuity')
        decision = action(event['action']); used = event['rule_charge']
        require(type(used) is int and 0 <= used <= expected['budget']['rule_applications_remaining'], 'rule_budget')
        expected['budget']['rule_applications_remaining'] -= used
        if decision['kind'] == 'check':
            check = decision['check_id']; family, price, outputs = CHECKS[check]
            values, _, _ = observations(expected); kind = expected['target']['kind']
            anchor = 'call_edge' if kind == 'call' else 'receiver_retained'
            require(values.get(anchor, {}).get('value') == ('static_external_resolved' if kind == 'call' else True), 'missing_anchor')
            require(expected['access'] == 'usable' and not expected['cancelled'], 'scope_unavailable')
            s, t = expected['scope'], expected['target']
            require(s['platform'] == 'synthetic_8_3_27' and s['compatibility'] == 'synthetic_v1' and s['execution'] != 'unknown', 'unsupported_scope')
            require(kind != 'call' or t['module_kind'] == 'common' and (t['route'] == 'same_context' or t['route'] == 'server_bridge' and s['execution'] == 'thin_client'), 'unsupported_scope')
            require(not (family == 'call' and kind != 'call' or family == 'receiver' and kind == 'call' or family == 'mismatch' and kind != 'mismatch'), 'wrong_check_target')
            require(check not in expected['attempted_checks'], 'duplicate_attempt')
            require({c['check_id']: c['state'] for c in expected['capabilities']}.get(check) == 'ready', 'consent_required')
            require(expected['budget']['observations_remaining'] > 0 and expected['budget']['cost_remaining'] >= price, 'budget_exhausted')
            if check == 'c11_receiver_shape':
                require(values.get('receiver_kind', {}).get('value') in WITNESSES, 'missing_prerequisite')
            require(check in case['outcomes'], 'missing_outcome')
            hidden = case['outcomes'][check]
            require(event['outcome'] == hidden, 'forged_reveal')
            observed = hidden['status'] == 'observed'
            require(set(f['predicate'] for f in hidden['facts']) == set(outputs) if observed else not hidden['facts'], 'incomplete_bundle')
            require(len(hidden['facts']) == len(outputs) if observed else not hidden['facts'], 'duplicate_bundle')
            for item in hidden['facts']:
                require(item['predicate'] not in values or values[item['predicate']] == item['value'], 'incompatible_reveal')
                if item['predicate'] == 'member_present':
                    require(item['value']['receiver_kind'] == values.get('receiver_kind', {}).get('value'), 'foreign_receiver_shape')
            expected['attempted_checks'].append(check); expected['sequence'] += 1
            expected['budget']['observations_remaining'] -= 1; expected['budget']['cost_remaining'] -= price
            attempts += 1; cost += price; disclosed += len(hidden['facts'])
            for item in hidden['facts']:
                ident = max([f['id'] for f in expected['facts']] + [0]) + 1
                old = [f['id'] for f in expected['facts'] if f['scope'] == expected['scope'] and f['target'] == expected['target'] and f['adapter'] == 'synthetic_v1' and f['predicate'] == item['predicate']]
                expected['facts'].append({'id': ident, 'scope': copy.deepcopy(expected['scope']), 'target': copy.deepcopy(expected['target']),
                    'predicate': item['predicate'], 'value': copy.deepcopy(item['value']), 'state': 'observed',
                    'adapter': 'synthetic_v1', 'adapter_version': 1, 'input_id': ident, 'check_id': check,
                    'sequence': expected['sequence'], 'valid_until': 65535, 'supersedes': old})
            require(event['receipt'] == {'check_id': check, 'status': hidden['status'], 'disclosed_facts': len(hidden['facts']), 'cost': price,
                                         'attempts_total': attempts, 'cost_total': cost}, 'forged_receipt')
        else:
            require(event['outcome'] is None and event['receipt'] is None, 'terminal_reveal')
            terminal = decision
        require(event['after'] == expected, 'ledger_changed')
        validate_envelope(expected)
    require(terminal is not None, 'missing_terminal')
    require(episode['totals'] == {'attempts': attempts, 'cost': cost, 'disclosed_facts': disclosed}, 'forged_totals')
    states, ids = findings(expected)
    active_ids = {ident for group in ids.values() for ident in group}
    require(set(terminal['evidence_ids']) <= active_ids, 'foreign_evidence')
    supported = set(terminal['supported']); refuted = set(terminal['refuted'])
    unjustified = sum(states.get(h) != 'supported' for h in supported) + sum(states.get(h) != 'refuted' for h in refuted)
    false_causes = len(supported - set(case['expected']['supported']))
    false_refutations = len(refuted - set(case['expected']['refuted']))
    # A correct label without its current supporting evidence is not a correct diagnosis.
    require(not supported and not refuted or bool(terminal['evidence_ids']), 'missing_evidence')
    cited = set(terminal['evidence_ids'])
    values, _, _ = observations(expected)
    anchor = 'call_edge' if expected['target']['kind'] == 'call' else 'receiver_retained'
    def group(predicates):
        return {ident for predicate in predicates for ident in ids.get(predicate, [])}
    for hypothesis in supported | refuted:
        choices = []
        if hypothesis == 'method_not_exported':
            choices = [group([anchor, 'exported'])]
        elif hypothesis == 'receiver_kind_mismatch':
            choices = [group([anchor, 'receiver_kind'])]
        elif hypothesis == 'immediate_member_absent':
            choices = [group([anchor, 'receiver_kind', 'member_present'])]
        elif hypothesis == 'call_context_unavailable':
            gates = ['context_enabled', 'compiled_copy_present'] + (['server_call_enabled'] if expected['target'].get('route') == 'server_bridge' else [])
            choices = [group([anchor, p]) for p in gates if values.get(p, {}).get('value') is False] if hypothesis in supported else [group([anchor, *gates])]
        elif hypothesis == 'source_runtime_mismatch':
            if hypothesis in supported:
                choices = [group([anchor, 'receiver_kind', 'member_present', 'source_member', 'object_correlation'])]
            else:
                if values.get('receiver_kind', {}).get('value') not in (None, 'application_object'):
                    choices.append(group([anchor, 'receiver_kind']))
                if values.get('member_present', {}).get('present') is True:
                    choices.append(group([anchor, 'receiver_kind', 'member_present']))
                for predicate, negative in [('source_member', 'absent_complete'), ('object_correlation', 'different_attested')]:
                    if values.get(predicate, {}).get('value') == negative:
                        choices.append(group([anchor, predicate]))
        if not any(proof and proof <= cited for proof in choices):
            unjustified += 1
    initial_states = findings(case['initial'])[0]
    case_findings = set(case['expected']['supported'])
    initial_only = episode['policy'] == 'model_one_shot'
    recall_target = case_findings & {h for h, state in initial_states.items() if state == 'supported'} if initial_only else case_findings
    return {'case_id': case['id'], 'initial_evidence_states': initial_states,
            'final_evidence_states': states, 'claimed_supported': sorted(supported),
            'claimed_refuted': sorted(refuted),
            'terminal_kind': terminal['kind'], 'false_causes': false_causes,
            'false_refutations': false_refutations, 'unjustified_findings': unjustified,
            'safe': false_causes + false_refutations + unjustified == 0,
            'finding_recall_numerator': len(supported & recall_target),
            'finding_recall_denominator': len(recall_target),
            'finding_recall_scope': 'initial_evidence_only' if initial_only else 'case_findings',
            'case_finding_recall_numerator': len(supported & case_findings),
            'case_finding_recall_denominator': len(case_findings),
            'abstention_scope': 'initial_evidence_only' if initial_only else 'observation_budget',
            'avoidable_abstention': terminal['kind'] == 'abstain' and bool(recall_target) and (initial_only or case['expected']['sufficient_possible']),
            'initial_evidence_only_abstention': initial_only and terminal['kind'] == 'abstain' and not recall_target,
            'budget_or_unavailable_abstention': not initial_only and terminal['kind'] == 'abstain' and not case['expected']['sufficient_possible'],
            'inconclusive': terminal['kind'] == 'unavailable', 'totals': episode['totals']}


def audit_schedule(cases, policies, records, criteria, criteria_sha256):
    """Evaluate a complete declared schedule and consume its frozen thresholds.

    The caller holds the expected criteria digest outside the evaluated records.
    This development evaluator does not manufacture independent utility labels.
    """
    require(hashlib.sha256(encoded(criteria)).hexdigest() == criteria_sha256, 'criteria_changed')
    require(criteria == {'schema': 1, 'mandatory_case_ids': sorted(c['id'] for c in cases),
        'policies': sorted(policies), 'max_false_causes': 0, 'max_false_refutations': 0,
        'max_unjustified_findings': 0}, 'unsupported_criteria')
    expected = {(c['id'], p) for c in cases for p in policies}
    observed = {(r['case_id'], r['policy']) for r in records}
    require(expected == observed and len(records) == len(expected), 'incomplete_schedule')
    by_id = {c['id']: c for c in cases}; scores = []
    for record in records:
        require(record['error'] is None, 'policy_failure')
        score = audit(by_id[record['case_id']], record)
        score['policy'] = record['policy']; scores.append(score)
    totals = {key: sum(s[key] for s in scores) for key in ['false_causes', 'false_refutations', 'unjustified_findings']}
    passed = all(totals[key] <= criteria['max_' + key] for key in totals)
    # Author-declared pairs remain development controls, never inferred fixes or
    # independent hidden labels. Preserve the two revisions and their outcomes.
    pairs = {}
    for case in cases:
        if case['phase'] != 'control':
            phases = pairs.setdefault(case['pair'], {})
            require(case['phase'] not in phases, 'duplicate_pair_phase')
            phases[case['phase']] = case
    paired_revisions = []
    for label, phases in sorted(pairs.items()):
        if set(phases) != {'before', 'after'}:
            continue
        for policy in policies:
            item = {'pair': label, 'policy': policy, 'scope': 'author_declared_development_control'}
            for phase in ['before', 'after']:
                case = phases[phase]
                score = next(s for s in scores if s['case_id'] == case['id'] and s['policy'] == policy)
                item[phase] = {'case_id': case['id'], 'revision_id': case['initial']['scope']['revision_id'],
                    'supported': score['claimed_supported'], 'refuted': score['claimed_refuted'],
                    'evidence_states': score['final_evidence_states'], 'safe': score['safe']}
            paired_revisions.append(item)
    return {'scores': scores, 'thresholds_consumed': True, 'ledger_and_findings_safe': passed,
            'mechanical_safety_passed': passed and not any(s['inconclusive'] for s in scores),
            'paired_revisions': paired_revisions,
            'next_check_accuracy': None,
            'next_check_accuracy_limitation': 'No independent admissible-next-action labels in public development controls',
            'per_policy': {p: {'episodes': sum(s['policy'] == p for s in scores),
                'finding_recall_scope': next(s['finding_recall_scope'] for s in scores if s['policy'] == p),
                'findings_recalled': sum(s['finding_recall_numerator'] for s in scores if s['policy'] == p),
                'findings_expected': sum(s['finding_recall_denominator'] for s in scores if s['policy'] == p),
                'requests': sum(s['totals']['attempts'] for s in scores if s['policy'] == p),
                'disclosed_facts': sum(s['totals']['disclosed_facts'] for s in scores if s['policy'] == p),
                'cost': sum(s['totals']['cost'] for s in scores if s['policy'] == p)} for p in policies}}
