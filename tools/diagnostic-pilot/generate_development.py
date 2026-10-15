"""Author the public MIT development controls; never a held-out case generator."""
import copy
import hashlib
import json
from pathlib import Path


def bit(value):
    return {'kind': 'bool', 'value': value}


def base(ident, family, pair='control', phase='control', kind='call'):
    target = {'kind': 'call', 'site': 1, 'module': 2, 'method': 3, 'module_kind': 'common', 'route': 'same_context'}
    caps = ['c01_call_copy', 'c02_call_flags']
    if kind != 'call':
        target = {'kind': 'receiver', 'site': 1, 'receiver': 2, 'member': 3, 'expected_kind': 'structure'}
        caps = ['c10_receiver_kind', 'c11_receiver_shape']
    if kind == 'mismatch':
        target = {'kind': 'mismatch', 'site': 1, 'receiver': 2, 'member': 3, 'source_type': 4, 'runtime_type': 5}
        caps += ['c20_source_presence', 'c21_object_correlation']
    envelope = {'schema_version': 1, 'rule_version': 1, 'catalog_version': 1,
        'scope': {'case_id': ident, 'snapshot_id': 2, 'revision_id': 2 if phase == 'after' else 1,
                  'session_id': 4, 'context_id': 5, 'platform': 'synthetic_8_3_27',
                  'compatibility': 'synthetic_v1', 'execution': 'thin_client'},
        'target': target, 'sequence': 1, 'access': 'usable', 'cancelled': False,
        'budget': {'observations_remaining': 3, 'cost_remaining': 9, 'rule_applications_remaining': 256},
        'attempted_checks': [], 'capabilities': [{'check_id': c, 'state': 'ready'} for c in caps], 'facts': []}
    result = {'id': ident, 'family': family, 'pair': pair, 'phase': phase, 'initial': envelope,
              'outcomes': {}, 'expected': {'supported': [], 'refuted': [], 'sufficient_possible': False},
              'provenance': {'license': 'MIT', 'origin': 'owned_synthetic_control', 'heldout': False, 'native_verified': False}}
    add(result, 'call_edge' if kind == 'call' else 'receiver_retained',
        {'kind': 'edge', 'value': 'static_external_resolved'} if kind == 'call' else bit(True))
    return result


def add(case, predicate, value):
    e = case['initial']; ident = len(e['facts']) + 1
    e['facts'].append({'id': ident, 'scope': copy.deepcopy(e['scope']), 'target': copy.deepcopy(e['target']),
        'predicate': predicate, 'value': value, 'state': 'observed', 'adapter': 'synthetic_v1',
        'adapter_version': 1, 'input_id': ident, 'check_id': None, 'sequence': 1,
        'valid_until': 65535, 'supersedes': []})


def outcome(case, check, **facts):
    case['outcomes'][check] = {'status': 'observed', 'facts': [{'predicate': p, 'value': v} for p, v in facts.items()]}


def call_world(case, context=True, exported=True, copy_present=True):
    outcome(case, 'c01_call_copy', compiled_copy_present=bit(copy_present))
    outcome(case, 'c02_call_flags', context_enabled=bit(context), server_call_enabled=bit(True), exported=bit(exported))


def author():
    cases = []
    for ident, exported, phase in [(1, False, 'before'), (2, True, 'after')]:
        c = base(ident, 'export_revision_pair', 'pair_001', phase); call_world(c, exported=exported)
        c['expected'] = {'supported': [] if exported else ['method_not_exported'],
            'refuted': ['call_context_unavailable', 'method_not_exported'] if exported else ['call_context_unavailable'], 'sufficient_possible': True}
        cases.append(c)
    c = base(3, 'context_unavailable'); call_world(c, context=False)
    c['expected'] = {'supported': ['call_context_unavailable'], 'refuted': ['method_not_exported'], 'sufficient_possible': True}; cases.append(c)
    for ident, present, family in [(4, False, 'structure_absent_key'), (5, True, 'structure_key_with_undefined')]:
        c = base(ident, family, kind='receiver')
        outcome(c, 'c10_receiver_kind', receiver_kind={'kind': 'receiver_kind', 'value': 'structure'})
        outcome(c, 'c11_receiver_shape', member_present={'kind': 'shape', 'present': present, 'receiver_kind': 'structure', 'witness': 'key_presence'})
        c['expected'] = {'supported': [] if present else ['immediate_member_absent'],
            'refuted': ['receiver_kind_mismatch', 'immediate_member_absent'] if present else ['receiver_kind_mismatch'], 'sufficient_possible': True}; cases.append(c)
    c = base(6, 'unavailable_shape', kind='receiver'); c['initial']['capabilities'] = []
    add(c, 'receiver_kind', {'kind': 'receiver_kind', 'value': 'structure'})
    c['expected']['refuted'] = ['receiver_kind_mismatch']; cases.append(c)
    c = base(7, 'two_conflicting_premises'); call_world(c, context=False)
    for p in ['compiled_copy_present', 'context_enabled']:
        add(c, p, bit(True)); add(c, p, bit(False))
    add(c, 'exported', bit(True))
    c['expected'] = {'supported': ['call_context_unavailable'], 'refuted': ['method_not_exported'], 'sufficient_possible': True}; cases.append(c)
    c = base(8, 'source_runtime_mismatch', kind='mismatch')
    add(c, 'receiver_kind', {'kind': 'receiver_kind', 'value': 'application_object'})
    outcome(c, 'c11_receiver_shape', member_present={'kind': 'shape', 'present': False, 'receiver_kind': 'application_object', 'witness': 'session_metadata'})
    outcome(c, 'c20_source_presence', source_member={'kind': 'source_presence', 'value': 'present'})
    outcome(c, 'c21_object_correlation', object_correlation={'kind': 'correlation', 'value': 'same_attested'})
    c['initial']['capabilities'] = [x for x in c['initial']['capabilities'] if x['check_id'] != 'c10_receiver_kind']
    c['expected'] = {'supported': ['source_runtime_mismatch'], 'refuted': [], 'sufficient_possible': True}; cases.append(c)
    c = base(9, 'unverified_object_correlation', kind='mismatch'); c['initial']['capabilities'] = []
    add(c, 'receiver_kind', {'kind': 'receiver_kind', 'value': 'application_object'})
    add(c, 'member_present', {'kind': 'shape', 'present': False, 'receiver_kind': 'application_object', 'witness': 'session_metadata'})
    add(c, 'source_member', {'kind': 'source_presence', 'value': 'present'})
    add(c, 'object_correlation', {'kind': 'correlation', 'value': 'unverified'}); cases.append(c)
    c = base(10, 'foreign_revision'); call_world(c)
    c['initial']['scope']['revision_id'] = 2; c['initial']['facts'][0]['scope']['revision_id'] = 2
    add(c, 'exported', bit(False)); c['initial']['facts'][-1]['scope']['revision_id'] = 1
    c['initial']['capabilities'] = []; cases.append(c)
    c = base(11, 'timeout_is_not_false'); call_world(c)
    c['outcomes']['c02_call_flags'] = {'status': 'timeout', 'facts': []}; cases.append(c)
    c = base(12, 'pending_consent'); call_world(c, exported=False)
    c['initial']['capabilities'][1]['state'] = 'consent_required'
    c['expected']['supported'] = ['method_not_exported']; cases.append(c)
    c = base(13, 'unsupported_form'); c['initial']['target']['module_kind'] = 'form'
    c['initial']['facts'][0]['target']['module_kind'] = 'form'; cases.append(c)
    c = base(14, 'coexisting_findings'); call_world(c, context=False, exported=False)
    c['expected'] = {'supported': ['call_context_unavailable', 'method_not_exported'], 'refuted': [], 'sufficient_possible': True}; cases.append(c)
    return cases


if __name__ == '__main__':
    directory = Path(__file__).parent / 'diagnostic_pilot/cases'; directory.mkdir(exist_ok=True)
    raw = (json.dumps(author(), indent=2, sort_keys=True) + '\n').encode()
    (directory / 'development.json').write_bytes(raw)
    manifest = {'schema': 1, 'license': 'MIT', 'origin': 'owned_synthetic_controls', 'heldout': False, 'native_verified': False,
        'files': [{'path': 'development.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}]}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
