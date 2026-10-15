"""Actual pinned provider + owned HTTP peer; never a real-model benchmark."""
from contextlib import contextmanager, redirect_stdout
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnostic_pilot.broker import Broker
from diagnostic_pilot.contracts import Invalid, encoded
from diagnostic_pilot.corpus import load
from diagnostic_pilot.one_shot_worker import EFFECTIVE_SETTINGS, SYSTEM_PROMPT as ONE_SHOT_PROMPT
from diagnostic_pilot.policies import ModelOneShot, ReadyAgent
from diagnostic_pilot.ready_worker import MODEL_SETTINGS, SYSTEM_PROMPT
from diagnostic_pilot.run import main, report


def decision(**changes):
    return {'kind': 'abstain', 'supported': [], 'refuted': [], 'evidence_ids': [],
            'reason': 'insufficient_data', **changes}


def tool_response(value=None, name='Decision'):
    return {'role': 'assistant', 'content': '',
            'tool_calls': [{'function': {'name': name, 'arguments': decision() if value is None else value}}]}


@contextmanager
def peer(message=None, *, usage=True, status=200, probe_status=200):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def respond(self, value, code=200):
            raw = (json.dumps(value) + '\n').encode()
            self.send_response(code); self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            self.respond({'models': [{'name': 'synthetic-http-peer'}]}, probe_status)
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            value = {'model': 'synthetic-http-peer', 'created_at': '2026-10-15T00:00:00Z',
                'message': tool_response() if message is None else message, 'done': True, 'done_reason': 'stop'}
            if usage:
                value.update(prompt_eval_count=12, eval_count=4)
            self.respond(value if status == 200 else {'error': 'private provider error text'}, status)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@unittest.skipUnless(importlib.util.find_spec('langchain') and importlib.util.find_spec('langchain_ollama'), 'Optional real framework dependencies not installed')
class OneShotFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.cases = load(ROOT / 'diagnostic_pilot/cases')

    def run_one(self, endpoint, case=None):
        return report(self.manifest, [case or self.cases[0]],
            {'model_one_shot': lambda: ModelOneShot('synthetic-http-peer', endpoint, timeout=20)})

    def initial_proof_case(self):
        # Owned initial-fact unit fixture; the public corpus remains unchanged.
        # This tests protocol admission, not independent or native evidence.
        case = copy.deepcopy(self.cases[0])
        fact = copy.deepcopy(case['initial']['facts'][0])
        fact.update(id=2, input_id=2, predicate='exported', value={'kind': 'bool', 'value': False})
        case['initial']['facts'].append(fact)
        return case

    def test_one_actual_request_matches_provider_settings_schema_and_initial_view(self):
        with peer() as (endpoint, requests):
            result = self.run_one(endpoint)
            ready = report(self.manifest, [self.cases[0]],
                {'ready_agent': lambda: ReadyAgent('synthetic-http-peer', endpoint, timeout=20)})
        self.assertEqual(len(requests), 2)
        first, second = requests
        self.assertEqual(first['model'], second['model'])
        self.assertEqual(first['options'], second['options'])
        one_tools = {t['function']['name']: t for t in first['tools']}
        ready_tools = {t['function']['name']: t for t in second['tools']}
        self.assertEqual(set(one_tools), {'Decision'})
        self.assertEqual(set(ready_tools), {'Decision', 'request_check'})
        self.assertEqual(one_tools['Decision'], ready_tools['Decision'])
        self.assertEqual(first['messages'][0]['content'], ONE_SHOT_PROMPT)
        self.assertEqual(second['messages'][0]['content'], SYSTEM_PROMPT)
        self.assertNotEqual(ONE_SHOT_PROMPT, SYSTEM_PROMPT)
        self.assertEqual(first['messages'][1], second['messages'][1])
        visible = json.loads(first['messages'][1]['content'])
        self.assertEqual(visible, Broker(self.cases[0]).view())
        self.assertEqual(set(visible), {'envelope', 'checks'})
        self.assertEqual(result['execution_status'], 'completed')
        self.assertEqual(ready['execution_status'], 'completed')
        self.assertEqual(result['records'][0]['totals'], {'attempts': 0, 'cost': 0, 'disclosed_facts': 0})
        measured, = result['records'][0]['metrics']
        self.assertEqual((measured['model_requests'], measured['input_tokens'], measured['output_tokens']), (1, 12, 4))
        score, = result['scores']
        self.assertFalse(score['avoidable_abstention'])
        self.assertTrue(score['initial_evidence_only_abstention'])
        self.assertEqual(score['finding_recall_scope'], 'initial_evidence_only')
        self.assertEqual(score['finding_recall_denominator'], 0)
        self.assertGreater(score['case_finding_recall_denominator'], 0)
        profile = result['policy_profiles']['model_one_shot']
        self.assertEqual((profile['maximum_model_requests'], profile['new_observations_allowed'], profile['new_observation_cost_allowed']), (1, 0, 0))
        self.assertTrue(all(result[k] is False for k in ['native_acceptance', 'heldout_independence', 'ai_competence_accepted']))

    def test_supported_initial_evidence_can_produce_a_safe_one_request_diagnosis(self):
        case = self.initial_proof_case()
        answer = decision(kind='diagnosis', supported=['method_not_exported'], evidence_ids=[1, 2], reason='bounded_finding')
        with peer(tool_response(answer)) as (endpoint, requests):
            result = self.run_one(endpoint, case)
        self.assertEqual(len(requests), 1)
        self.assertTrue(result['mechanical_safety_passed'])
        self.assertEqual(result['records'][0]['totals'], {'attempts': 0, 'cost': 0, 'disclosed_facts': 0})
        self.assertEqual(result['scores'][0]['finding_recall_numerator'], 1)
        self.assertEqual(result['scores'][0]['finding_recall_denominator'], 1)
        with peer() as (endpoint, requests):
            abstained = self.run_one(endpoint, case)
        self.assertTrue(abstained['scores'][0]['avoidable_abstention'])

    def test_both_real_framework_paths_refuse_coerced_evidence_ids(self):
        case = self.initial_proof_case()
        for invalid in [True, 1.0, '1']:
            for name, policy, limit in [('model_one_shot', ModelOneShot, 1),
                                       ('ready_agent', ReadyAgent, MODEL_SETTINGS['maximum_requests'])]:
                with self.subTest(value=repr(invalid), policy=name):
                    answer = decision(kind='diagnosis', supported=['method_not_exported'],
                        evidence_ids=[invalid, 2], reason='bounded_finding')
                    with peer(tool_response(answer)) as (endpoint, requests):
                        result = report(self.manifest, [case],
                            {name: lambda: policy('synthetic-http-peer', endpoint, timeout=20)})
                    self.assertGreaterEqual(len(requests), 1)
                    self.assertLessEqual(len(requests), limit)
                    if name == 'model_one_shot':
                        self.assertEqual(len(requests), 1)
                    self.assertEqual(result['execution_status'], 'inconclusive')
                    self.assertFalse(result['mechanical_safety_passed'])
                    self.assertFalse(result['evaluation']['mechanical_safety_passed'])
                    self.assertEqual(result['scores'][0]['terminal_kind'], 'unavailable')
                    record, = result['records']
                    self.assertEqual(record['metrics'][0]['model_requests'], len(requests))
                    self.assertEqual(record['events'][0]['action']['evidence_ids'], [])
                    self.assertEqual(record['totals'], {'attempts': 0, 'cost': 0, 'disclosed_facts': 0})

    def test_invented_finding_is_rejected_by_common_evaluator_without_observations(self):
        answer = decision(kind='diagnosis', supported=['method_not_exported'], evidence_ids=[1], reason='bounded_finding')
        with peer(tool_response(answer)) as (endpoint, requests):
            result = self.run_one(endpoint)
        self.assertEqual(len(requests), 1)
        self.assertEqual(result['execution_status'], 'failed')
        self.assertFalse(result['mechanical_safety_passed'])
        self.assertFalse(result['ledger_and_findings_safe'])
        self.assertGreater(result['scores'][0]['unjustified_findings'], 0)
        self.assertEqual(result['records'][0]['totals']['attempts'], 0)

    def test_null_invalid_foreign_multiple_missing_usage_and_provider_error_never_retry(self):
        variants = [
            ('null', {'role': 'assistant', 'content': 'private model text'}, True, 200),
            ('schema', tool_response({'kind': 'check', 'check_id': 'c02_call_flags'}), True, 200),
            ('foreign_tool', tool_response({'check_id': 'c02_call_flags'}, name='request_check'), True, 200),
            ('multiple', {'role': 'assistant', 'content': '', 'tool_calls': tool_response()['tool_calls'] * 2}, True, 200),
            ('missing_usage', tool_response(), False, 200),
            ('provider_error', tool_response(), True, 500),
        ]
        for label, message, usage, status in variants:
            with self.subTest(label=label), peer(message, usage=usage, status=status) as (endpoint, requests):
                result = self.run_one(endpoint)
                self.assertEqual(len(requests), 1)
                self.assertEqual(result['execution_status'], 'inconclusive')
                self.assertFalse(result['mechanical_safety_passed'])
                self.assertFalse(result['evaluation']['mechanical_safety_passed'])
                self.assertEqual(result['scores'][0]['terminal_kind'], 'unavailable')
                self.assertEqual(result['records'][0]['metrics'][0]['model_requests'], 1)
                self.assertEqual(result['records'][0]['totals'], {'attempts': 0, 'cost': 0, 'disclosed_facts': 0})
                self.assertNotIn('private model text', json.dumps(result))
                self.assertNotIn('private provider error text', json.dumps(result))

    def test_second_host_decision_is_refused_without_a_second_request(self):
        with peer() as (endpoint, requests):
            policy = ModelOneShot('synthetic-http-peer', endpoint, timeout=20)
            try:
                view = Broker(self.cases[0]).view()
                self.assertEqual(policy.decide(view)[0]['kind'], 'abstain')
                with self.assertRaisesRegex(Invalid, 'one_shot_already_decided'):
                    policy.decide(view)
                self.assertEqual(len(requests), 1)
            finally:
                policy.close()

    def test_unavailable_provider_is_inconclusive_without_a_model_request(self):
        with peer(probe_status=503) as (endpoint, requests):
            result = self.run_one(endpoint)
        self.assertEqual(requests, [])
        self.assertEqual(result['execution_status'], 'inconclusive')
        self.assertFalse(result['mechanical_safety_passed'])
        self.assertFalse(result['evaluation']['mechanical_safety_passed'])
        self.assertEqual(result['records'][0]['metrics'][0]['model_requests'], 0)
        self.assertEqual(result['records'][0]['events'][0]['action']['reason'], 'model_unavailable')

    def test_cli_receipt_records_effective_ablation_prompt_settings_and_source(self):
        with tempfile.TemporaryDirectory() as temporary, peer() as (endpoint, requests):
            output = Path(temporary) / 'receipt.json'
            with redirect_stdout(io.StringIO()):
                status = main(['--policies', 'model_one_shot', '--model', 'synthetic-http-peer', '--endpoint', endpoint,
                    '--case-id', '1', '--output', str(output)])
            result = json.loads(output.read_bytes())
        self.assertEqual(status, 0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(result['runtime']['model_name'], 'synthetic-http-peer')
        self.assertEqual(result['runtime']['system_prompt_sha256'], hashlib.sha256(ONE_SHOT_PROMPT.encode()).hexdigest())
        self.assertEqual(result['runtime']['model_settings'], EFFECTIVE_SETTINGS)
        self.assertEqual({k: v for k, v in EFFECTIVE_SETTINGS.items() if k != 'maximum_requests'},
            {k: v for k, v in MODEL_SETTINGS.items() if k != 'maximum_requests'})
        self.assertEqual(result['runtime']['model_settings_sha256'], hashlib.sha256(encoded(EFFECTIVE_SETTINGS)).hexdigest())
        self.assertEqual(result['runtime']['model_artifact_verification'], 'not_verified_by_harness')
        self.assertIsNone(result['runtime']['model_artifact_digest'])
        self.assertEqual(result['implementation_sha256']['one_shot_worker.py'],
            hashlib.sha256((ROOT / 'diagnostic_pilot/one_shot_worker.py').read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as temporary, peer() as (endpoint, requests):
            output = Path(temporary) / 'mixed.json'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--policies', 'model_one_shot', 'ready_agent', '--model', 'synthetic-http-peer',
                    '--endpoint', endpoint, '--case-id', '1', '--output', str(output)]), 0)
            mixed = json.loads(output.read_bytes())
        self.assertEqual(len(requests), 2)
        self.assertIsNone(mixed['runtime']['system_prompt_sha256'])
        self.assertIsNone(mixed['runtime']['model_settings'])
        self.assertIsNone(mixed['runtime']['model_settings_sha256'])
        self.assertEqual(mixed['policy_profiles']['model_one_shot']['maximum_model_requests'], 1)
        self.assertEqual(mixed['policy_profiles']['ready_agent']['maximum_model_requests'], 8)


if __name__ == '__main__':
    unittest.main()
