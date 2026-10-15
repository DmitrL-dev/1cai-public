"""Run actual policies against hash-bound owned development controls."""
import argparse
import copy
import hashlib
import importlib.metadata
from pathlib import Path
import sys
import time

from .broker import Broker
from .contracts import Invalid, action, encoded, require
from .corpus import load
from .evaluate import audit, audit_schedule
from .policies import FixedOrder, OnePass, ReadyAgent, RustPolicy, terminal
from .ready_worker import MODEL_SETTINGS, PINS, SYSTEM_PROMPT


def source_hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).resolve().parent.glob('*.py'))}


def episode(case, policy):
    broker = Broker(case); events = []; metrics = []; error = None
    started = time.monotonic()
    try:
        for _ in range(4):
            before = broker.view()['envelope']
            decision, charge, measured = policy.decide(broker.view())
            decision = action(decision)
            broker.charge_reasoning(charge)
            receipt = outcome = None
            if decision['kind'] == 'check':
                receipt = broker.request(decision['check_id'])
                # The policy saw this reveal; no unrequested outcome is journalled.
                outcome = copy.deepcopy(case['outcomes'][decision['check_id']])
            events.append({'before': before, 'action': decision, 'rule_charge': charge,
                           'outcome': outcome, 'receipt': receipt, 'after': broker.view()['envelope']})
            metrics.append(measured)
            if decision['kind'] != 'check':
                break
        else:
            raise Invalid('policy_turn_limit')
    except (Invalid, OSError, ValueError, KeyError):
        error = 'policy_or_contract_failed'
    finally:
        policy.close()
    return {'case_id': case['id'], 'policy': policy.name, 'events': events, 'totals': broker.totals(),
            'metrics': metrics, 'wall_milliseconds': int((time.monotonic() - started) * 1000), 'error': error}


def report(manifest, cases, factories):
    records = []; scores = []; errors = []
    require(bool(cases) and bool(factories), 'empty_schedule')
    for name, factory in factories.items():
        for case in cases:
            record = episode(case, factory()); records.append(record)
            try:
                require(record['error'] is None, 'policy_failure')
                score = audit(case, record); score['policy'] = name; scores.append(score)
            except (Invalid, KeyError, TypeError):
                errors.append({'case_id': case['id'], 'policy': name, 'code': 'invalid_or_failed_episode'})
    expected = {(case['id'], policy) for case in cases for policy in factories}
    observed = {(record['case_id'], record['policy']) for record in records}
    require(expected == observed and len(records) == len(expected), 'incomplete_schedule')
    criteria = {'schema': 1, 'mandatory_case_ids': sorted(c['id'] for c in cases),
        'policies': sorted(factories), 'max_false_causes': 0, 'max_false_refutations': 0,
        'max_unjustified_findings': 0}
    criteria_hash = hashlib.sha256(encoded(criteria)).hexdigest()
    schedule = None
    if not errors:
        schedule = audit_schedule(cases, list(factories), records, criteria, criteria_hash)
    inconclusive = any(s['inconclusive'] for s in scores)
    safe = not errors and all(s['safe'] for s in scores)
    return {'schema': 1, 'scope': 'owned public development controls; not independent heldout or native/LLM competence acceptance',
        'corpus_manifest_sha256': hashlib.sha256(encoded(manifest)).hexdigest(),
        'schedule_complete': True, 'episodes': len(records), 'policies': list(factories),
        'ledger_and_findings_safe': safe, 'mechanical_safety_passed': safe and not inconclusive,
        'execution_status': 'failed' if not safe else 'inconclusive' if inconclusive else 'completed',
        'native_acceptance': False, 'heldout_independence': False, 'ai_competence_accepted': False,
        'criteria': criteria, 'criteria_sha256': criteria_hash,
        'evaluation': schedule, 'scores': scores, 'errors': errors, 'records': records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path(__file__).resolve().parent / 'cases')
    parser.add_argument('--policies', nargs='+', choices=['fixed', 'one_pass', 'rust', 'ready_agent', 'hybrid'], default=['fixed', 'rust'])
    parser.add_argument('--rust-binary', type=Path); parser.add_argument('--rust-sha256')
    parser.add_argument('--model'); parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--case-id', type=int, action='append', help='Explicit development smoke subset; never whole-corpus acceptance')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    implementation = source_hashes()
    require(len(args.policies) == len(set(args.policies)), 'duplicate_policy')
    manifest, cases = load(args.corpus)
    corpus_case_ids = [case['id'] for case in cases]
    if args.case_id:
        require(len(args.case_id) == len(set(args.case_id)) and set(args.case_id) <= set(corpus_case_ids), 'unknown_case_selection')
        cases = [case for case in cases if case['id'] in args.case_id]
    if 'rust' in args.policies or 'hybrid' in args.policies:
        require(args.rust_binary is not None and args.rust_sha256 is not None, 'explicit_rust_binary_required')
    if {'ready_agent', 'hybrid'} & set(args.policies):
        require(args.model is not None, 'explicit_local_model_required')
    factories = {}
    for name in args.policies:
        if name == 'fixed': factories[name] = FixedOrder
        elif name == 'one_pass': factories[name] = OnePass
        elif name == 'rust': factories[name] = lambda: RustPolicy(args.rust_binary, args.rust_sha256)
        elif name == 'ready_agent': factories[name] = lambda: ReadyAgent(args.model, args.endpoint)
        else: factories[name] = lambda: ReadyAgent(args.model, args.endpoint, rust=RustPolicy(args.rust_binary, args.rust_sha256))
    result = report(manifest, cases, factories)
    result['selected_case_ids'] = [case['id'] for case in cases]
    result['whole_corpus_schedule_complete'] = set(result['selected_case_ids']) == set(corpus_case_ids)
    result['runtime'] = {'python': sys.version.split()[0], 'platform': sys.platform,
                         'rust_binary_sha256': args.rust_sha256 if 'rust' in factories or 'hybrid' in factories else None,
                         'model_name': args.model if {'ready_agent', 'hybrid'} & set(factories) else None}
    framework_versions = {}
    for package in sorted(set(PINS) | {'langchain-core', 'langgraph', 'langgraph-prebuilt',
                                      'langgraph-checkpoint', 'langgraph-sdk', 'ollama', 'pydantic'}):
        try:
            framework_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            framework_versions[package] = None
    lock = Path(__file__).resolve().parent / 'requirements-ready.lock'
    if not lock.is_file():
        lock = lock.parent.parent / 'requirements-ready.lock'
    result['runtime'].update({'framework_versions': framework_versions,
        'requirements_lock_sha256': hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else None,
        'system_prompt_sha256': hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        'model_settings': MODEL_SETTINGS, 'model_settings_sha256': hashlib.sha256(encoded(MODEL_SETTINGS)).hexdigest(),
        'model_artifact_digest': None, 'model_artifact_verification': 'not_verified_by_harness'})
    require(source_hashes() == implementation, 'implementation_changed_during_run')
    result['implementation_sha256'] = implementation
    with args.output.open('xb') as target:
        target.write(encoded(result) + b'\n')
    print(encoded({key: result[key] for key in ['execution_status', 'episodes', 'mechanical_safety_passed', 'native_acceptance', 'heldout_independence', 'ai_competence_accepted']}).decode())
    return 1 if result['execution_status'] == 'failed' else 2 if result['execution_status'] == 'inconclusive' else 0


if __name__ == '__main__':
    raise SystemExit(main())
