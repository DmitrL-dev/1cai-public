"""Real optional framework + controlled HTTP peer, not a real-model benchmark."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnostic_pilot.corpus import load
from diagnostic_pilot.policies import ReadyAgent
from diagnostic_pilot.run import report


@unittest.skipUnless(importlib.util.find_spec('langchain') and importlib.util.find_spec('langchain_ollama'), 'Optional real framework dependencies not installed')
class ReadyFrameworkTests(unittest.TestCase):
    def test_real_framework_without_structured_decision_is_inconclusive_not_pass(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def respond(self, value):
                raw = (json.dumps(value) + '\n').encode()
                self.send_response(200); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                self.respond({'models': [{'name': 'synthetic-http-peer'}]})
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.respond({'model': 'synthetic-http-peer', 'created_at': '2026-10-15T00:00:00Z',
                    'message': {'role': 'assistant', 'content': 'Unstructured development peer response.'},
                    'done': True, 'done_reason': 'stop', 'prompt_eval_count': 12, 'eval_count': 4})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            manifest, cases = load(ROOT / 'diagnostic_pilot/cases')
            result = report(manifest, [cases[0]], {'ready_agent': lambda: ReadyAgent('synthetic-http-peer', f'http://127.0.0.1:{server.server_port}', timeout=20)})
            self.assertEqual(result['execution_status'], 'inconclusive')
            self.assertFalse(result['mechanical_safety_passed'])
            self.assertTrue(result['ledger_and_findings_safe'])
            measured, = result['records'][0]['metrics']
            self.assertEqual(measured['structured_response_type'], 'null')
            self.assertEqual(measured['failure_stage'], 'structured_response_missing')
            self.assertEqual(measured['failure_class'], 'Invalid')
            self.assertEqual(measured['failure_code'], 'structured_response_missing')
            self.assertNotIn('Unstructured development peer response', json.dumps(result))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_actual_create_agent_tool_loop_uses_only_broker_and_scores_final_response(self):
        class Handler(BaseHTTPRequestHandler):
            calls = 0
            tool_sets = []
            def log_message(self, *args): pass
            def respond(self, value):
                raw = (json.dumps(value) + '\n').encode()
                self.send_response(200); self.send_header('Content-Type', 'application/x-ndjson')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                self.respond({'models': [{'name': 'synthetic-http-peer'}]})
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                Handler.tool_sets.append({t['function']['name'] for t in request['tools']})
                Handler.calls += 1
                if Handler.calls == 1:
                    name, args = 'request_check', {'check_id': 'c02_call_flags'}
                else:
                    name, args = 'Decision', {'kind': 'diagnosis', 'supported': ['method_not_exported'],
                        'refuted': [], 'evidence_ids': [1, 4], 'reason': 'bounded_finding'}
                self.respond({'model': 'synthetic-http-peer', 'created_at': '2026-10-15T00:00:00Z',
                    'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': name, 'arguments': args}}]},
                    'done': True, 'done_reason': 'stop', 'prompt_eval_count': 12, 'eval_count': 4,
                    'total_duration': 10000, 'load_duration': 0, 'prompt_eval_duration': 1000, 'eval_duration': 1000})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            manifest, cases = load(ROOT / 'diagnostic_pilot/cases')
            result = report(manifest, [cases[0]], {'ready_agent': lambda: ReadyAgent('synthetic-http-peer', f'http://127.0.0.1:{server.server_port}', timeout=20)})
            self.assertEqual(result['execution_status'], 'completed', result['errors'])
            self.assertTrue(result['mechanical_safety_passed'])
            self.assertEqual(Handler.calls, 2)
            self.assertTrue(all(names == {'request_check', 'Decision'} for names in Handler.tool_sets))
            self.assertEqual(result['records'][0]['metrics'][-1]['model_requests'], 2)
            self.assertEqual(result['records'][0]['metrics'][-1]['input_tokens'], 24)
            self.assertEqual(result['scores'][0]['totals']['attempts'], 1)
            self.assertFalse(result['ai_competence_accepted'])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
