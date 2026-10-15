"""Closed, bounded wire admission shared by host adapters, never a fact oracle."""
import copy
import json
import re

CHECKS = {
    'c01_call_copy': ('call', 1, ('compiled_copy_present',)),
    'c02_call_flags': ('call', 3, ('context_enabled', 'server_call_enabled', 'exported')),
    'c10_receiver_kind': ('receiver', 1, ('receiver_kind',)),
    'c11_receiver_shape': ('receiver', 1, ('member_present',)),
    'c20_source_presence': ('mismatch', 1, ('source_member',)),
    'c21_object_correlation': ('mismatch', 1, ('object_correlation',)),
}
HYPOTHESES = {'call_context_unavailable', 'method_not_exported', 'immediate_member_absent',
              'receiver_kind_mismatch', 'source_runtime_mismatch'}
KINDS = {'structure', 'query_result', 'query_selection', 'application_object', 'other'}
STATES = {'observed', 'unavailable', 'stale', 'conflicting', 'revoked'}
BOOLS = {'context_enabled', 'server_call_enabled', 'exported', 'compiled_copy_present', 'receiver_retained'}
WITNESSES = {'structure': 'key_presence', 'query_result': 'query_schema',
             'query_selection': 'query_schema', 'application_object': 'session_metadata'}
REASONS = {'bounded_finding', 'insufficient_data', 'budget_exhausted', 'all_refuted',
           'unsupported_scope', 'cancelled', 'access_revoked', 'dependency_missing',
           'model_unavailable', 'policy_error', 'pending_consent'}


class Invalid(ValueError):
    """Finite failure code; untrusted text is never reflected in errors."""


def require(condition, code):
    if not condition:
        raise Invalid(code)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), 'invalid_fields')


def integer(value, lower=0, upper=65535):
    require(type(value) is int and lower <= value <= upper, 'invalid_integer')


def enum(value, options):
    require(type(value) is str and value in options, 'invalid_enum')


def bounded_json(raw, maximum=65536):
    require(type(raw) is bytes and len(raw) <= maximum, 'input_limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_key')
            result[key] = value
        return result
    def unsigned(text):
        require(re.fullmatch('[0-9]+', text) is not None, 'invalid_integer')
        return int(text)
    def invalid(_):
        raise Invalid('invalid_number')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                           parse_int=unsigned, parse_float=invalid, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Invalid('invalid_json') from None
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        require(depth <= 16, 'depth_limit')
        if type(item) is dict:
            stack.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            stack.extend((v, depth + 1) for v in item)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def scope(value):
    exact(value, 'case_id snapshot_id revision_id session_id context_id platform compatibility execution')
    for key in ['case_id', 'snapshot_id', 'revision_id', 'session_id', 'context_id']:
        integer(value[key], 1)
    enum(value['platform'], {'synthetic_8_3_27', 'unsupported'})
    enum(value['compatibility'], {'synthetic_v1', 'unsupported'})
    enum(value['execution'], {'server', 'thin_client', 'unknown'})


def target(value):
    require(type(value) is dict and 'kind' in value, 'invalid_target')
    kind = value['kind']
    enum(kind, {'call', 'receiver', 'mismatch'})
    fields = {'call': 'kind site module method module_kind route',
              'receiver': 'kind site receiver member expected_kind',
              'mismatch': 'kind site receiver member source_type runtime_type'}[kind]
    exact(value, fields)
    for key, item in value.items():
        if key not in {'kind', 'module_kind', 'route', 'expected_kind'}:
            integer(item, 1)
    if kind == 'call':
        enum(value['module_kind'], {'common', 'form'})
        enum(value['route'], {'same_context', 'server_bridge', 'dynamic'})
    if kind == 'receiver':
        enum(value['expected_kind'], KINDS)


def fact_value(predicate, value):
    if predicate in BOOLS:
        exact(value, 'kind value'); require(value['kind'] == 'bool' and type(value['value']) is bool, 'invalid_value')
    elif predicate in {'call_edge', 'receiver_kind', 'source_member', 'object_correlation'}:
        exact(value, 'kind value')
        tag, choices = {'call_edge': ('edge', {'static_external_resolved', 'unresolved', 'dynamic'}),
                        'receiver_kind': ('receiver_kind', KINDS),
                        'source_member': ('source_presence', {'present', 'absent_complete', 'unresolved'}),
                        'object_correlation': ('correlation', {'same_attested', 'different_attested', 'unverified'})}[predicate]
        require(value['kind'] == tag, 'invalid_value'); enum(value['value'], choices)
    elif predicate == 'member_present':
        exact(value, 'kind present receiver_kind witness')
        require(value['kind'] == 'shape' and type(value['present']) is bool, 'invalid_value')
        enum(value['receiver_kind'], WITNESSES)
        require(value['witness'] == WITNESSES[value['receiver_kind']], 'invalid_shape')
    else:
        raise Invalid('invalid_predicate')


def validate_fact(value):
    exact(value, 'id scope target predicate value state adapter adapter_version input_id check_id sequence valid_until supersedes')
    for key in ['id', 'input_id']:
        integer(value[key], 1)
    scope(value['scope']); target(value['target'])
    enum(value['state'], STATES); enum(value['adapter'], {'synthetic_v1', 'untrusted', 'unverified_zip'})
    require(value['adapter_version'] == 1 and type(value['adapter_version']) is int, 'invalid_version')
    fact_value(value['predicate'], value['value'])
    allowed = {'call': {'call_edge', 'compiled_copy_present', 'context_enabled', 'server_call_enabled', 'exported'},
               'receiver': {'receiver_retained', 'receiver_kind', 'member_present'},
               'mismatch': {'receiver_retained', 'receiver_kind', 'member_present', 'source_member', 'object_correlation'}}
    require(value['predicate'] in allowed[value['target']['kind']], 'foreign_predicate')
    integer(value['sequence']); integer(value['valid_until'])
    require(value['sequence'] <= value['valid_until'], 'invalid_validity')
    require(type(value['supersedes']) is list and len(value['supersedes']) <= 128, 'invalid_supersession')
    for item in value['supersedes']:
        integer(item, 1)
    require(len(set(value['supersedes'])) == len(value['supersedes']), 'invalid_supersession')
    if value['check_id'] is not None:
        enum(value['check_id'], CHECKS)
        require(value['predicate'] in CHECKS[value['check_id']][2], 'invalid_check_binding')


def validate_envelope(value):
    exact(value, 'schema_version rule_version catalog_version scope target sequence access cancelled budget attempted_checks capabilities facts')
    for key in ['schema_version', 'rule_version', 'catalog_version']:
        require(type(value[key]) is int and value[key] == 1, 'invalid_version')
    scope(value['scope']); target(value['target']); integer(value['sequence'])
    enum(value['access'], {'usable', 'revoked'}); require(type(value['cancelled']) is bool, 'invalid_cancelled')
    exact(value['budget'], 'observations_remaining cost_remaining rule_applications_remaining')
    for key, maximum in [('observations_remaining', 3), ('cost_remaining', 9), ('rule_applications_remaining', 256)]:
        integer(value['budget'][key], 0, maximum)
    require(type(value['attempted_checks']) is list and len(value['attempted_checks']) <= 3, 'attempt_limit')
    for check in value['attempted_checks']:
        enum(check, CHECKS)
    require(len(set(value['attempted_checks'])) == len(value['attempted_checks']), 'duplicate_attempt')
    require(value['budget']['observations_remaining'] + len(value['attempted_checks']) <= 3, 'reset_budget')
    require(value['budget']['cost_remaining'] + sum(CHECKS[c][1] for c in value['attempted_checks']) <= 9, 'reset_budget')
    require(type(value['capabilities']) is list and len(value['capabilities']) <= 6, 'invalid_capabilities')
    seen = set()
    for cap in value['capabilities']:
        exact(cap, 'check_id state'); enum(cap['check_id'], CHECKS)
        enum(cap['state'], {'ready', 'consent_required', 'unavailable'})
        require(cap['check_id'] not in seen, 'duplicate_capability'); seen.add(cap['check_id'])
    require(type(value['facts']) is list and len(value['facts']) <= 128, 'fact_limit')
    facts = {}
    for fact in value['facts']:
        validate_fact(fact); require(fact['id'] not in facts, 'duplicate_fact'); facts[fact['id']] = fact
        require(fact['check_id'] is None or fact['check_id'] in value['attempted_checks'], 'missing_attempt')
    edges = 0
    for fact in facts.values():
        edges += len(fact['supersedes'])
        for predecessor in fact['supersedes']:
            require(predecessor in facts, 'missing_predecessor')
            old = facts[predecessor]
            require(all(fact[k] == old[k] for k in ['scope', 'target', 'predicate', 'adapter', 'adapter_version']), 'foreign_supersession')
            require(old['sequence'] < fact['sequence'] <= value['sequence'] and fact['adapter'] == 'synthetic_v1'
                    and fact['state'] in {'observed', 'stale', 'revoked'}, 'invalid_supersession')
    require(edges <= 128, 'edge_limit')
    return copy.deepcopy(value)


def action(value):
    require(type(value) is dict, 'invalid_action')
    kind = value.get('kind')
    if kind == 'check':
        exact(value, 'kind check_id'); enum(value['check_id'], CHECKS)
    else:
        exact(value, 'kind supported refuted evidence_ids reason')
        enum(kind, {'diagnosis', 'abstain', 'unavailable'}); enum(value['reason'], REASONS)
        for field in ['supported', 'refuted']:
            require(type(value[field]) is list and len(value[field]) <= 5, 'invalid_finding')
            for name in value[field]:
                enum(name, HYPOTHESES)
            require(len(value[field]) == len(set(value[field])), 'duplicate_finding')
        require(not set(value['supported']) & set(value['refuted']), 'contradictory_finding')
        require(type(value['evidence_ids']) is list and len(value['evidence_ids']) <= 128, 'invalid_evidence')
        for ident in value['evidence_ids']:
            integer(ident, 1)
        require(len(value['evidence_ids']) == len(set(value['evidence_ids'])), 'duplicate_evidence')
        require(kind == 'diagnosis' or not value['supported'], 'invalid_abstention')
        require(kind != 'diagnosis' or bool(value['supported']), 'empty_diagnosis')
    return copy.deepcopy(value)
