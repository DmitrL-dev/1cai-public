"""Mechanics/mutation controls, never a substitute for a real AI/native run."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnostic_pilot.broker import Broker, active
from diagnostic_pilot.contracts import Invalid, action, bounded_json, encoded
from diagnostic_pilot.corpus import load
from diagnostic_pilot.evaluate import audit, audit_schedule, findings
from diagnostic_pilot.policies import FixedOrder, OnePass, ReadyAgent, terminal
from diagnostic_pilot.run import episode, main, report
from diagnostic_pilot.ready_worker import failure_detail


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.cases = load(ROOT / 'diagnostic_pilot/cases')

    def case(self, ident=1):
        return copy.deepcopy(next(c for c in self.cases if c['id'] == ident))

    def test_public_corpus_is_licensed_development_not_native_or_heldout(self):
        self.assertEqual(len(self.cases), 14)
        self.assertFalse(self.manifest['heldout']); self.assertFalse(self.manifest['native_verified'])
        a, b = self.case(1), self.case(2)
        self.assertEqual(a['pair'], b['pair'])
        self.assertNotEqual(a['initial']['scope']['revision_id'], b['initial']['scope']['revision_id'])

    def test_corpus_mutation_is_rejected_before_policy_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for original in (ROOT / 'diagnostic_pilot/cases').iterdir():
                (root / original.name).write_bytes(original.read_bytes())
            path = root / 'development.json'; path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(Invalid, 'corpus_hash_mismatch'):
                load(root)

    def test_oversize_corpus_reads_are_bounded_before_allocation(self):
        original_open = Path.open
        calls = []
        class Reader:
            def __init__(self, path):
                self.path = path; self.source = original_open(path, 'rb')
            def __enter__(self): return self
            def __exit__(self, *args): self.source.close()
            def read(self, maximum=-1):
                calls.append((self.path.name, maximum))
                self.assert_bounded(maximum)
                return self.source.read(maximum)
            @staticmethod
            def assert_bounded(maximum):
                if not 0 <= maximum <= 512 * 1024 + 1:
                    raise AssertionError('unbounded corpus read')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_bytes(b'x' * (8 * 1024 * 1024))
            with patch('diagnostic_pilot.corpus.Path.open', lambda path, mode: Reader(path)):
                with self.assertRaisesRegex(Invalid, 'input_limit'):
                    load(root)
            self.assertEqual(calls, [('manifest.json', 65537)])
            for original in (ROOT / 'diagnostic_pilot/cases').iterdir():
                (root / original.name).write_bytes(original.read_bytes())
            (root / 'development.json').write_bytes(b'x' * (8 * 1024 * 1024))
            calls.clear()
            with patch('diagnostic_pilot.corpus.Path.open', lambda path, mode: Reader(path)):
                with self.assertRaisesRegex(Invalid, 'corpus_hash_mismatch'):
                    load(root)
            self.assertEqual(calls, [('manifest.json', 65537), ('development.json', 52360)])

    def test_protocol_rejects_duplicate_numbers_depth_and_oversize(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":-0}', b'{"a":1.0}', b'{"a":NaN}', b'[' * 18 + b'0' + b']' * 18, b'x' * 65537]:
            with self.subTest(raw=raw[:24]), self.assertRaises(Invalid):
                bounded_json(raw)

    def test_policy_view_cannot_read_ground_truth_or_unrequested_outcomes(self):
        view = Broker(self.case()).view()
        self.assertEqual(set(view), {'envelope', 'checks'})
        for hidden in ['expected', 'outcomes', 'family', 'pair', 'provenance', 'heldout']:
            self.assertNotIn(hidden, encoded(view).decode())

    def test_two_step_conflict_repairs_are_legal_without_status_gain(self):
        broker = Broker(self.case(7))
        self.assertEqual({c['check_id'] for c in broker.view()['checks']}, {'c01_call_copy', 'c02_call_flags'})
        self.assertEqual(findings(broker.view()['envelope'])[0]['call_context_unavailable'], 'unknown')
        broker.request('c01_call_copy')
        self.assertEqual(findings(broker.view()['envelope'])[0]['call_context_unavailable'], 'unknown')
        broker.request('c02_call_flags')
        self.assertEqual(findings(broker.view()['envelope'])[0]['call_context_unavailable'], 'supported')

    def test_pending_consent_does_not_execute_or_spend_budget(self):
        broker = Broker(self.case(12)); before = broker.view()
        with self.assertRaisesRegex(Invalid, 'consent_required'):
            broker.request('c02_call_flags')
        self.assertEqual(broker.view(), before)
        self.assertEqual(broker.totals()['attempts'], 0)

    def test_repeated_check_is_refused_without_second_charge(self):
        broker = Broker(self.case()); broker.request('c01_call_copy'); before = broker.view()
        with self.assertRaisesRegex(Invalid, 'ineligible_check'):
            broker.request('c01_call_copy')
        self.assertEqual(broker.view(), before)

    def test_no_cost_or_observation_budget_cannot_start_check(self):
        for field, amount in [('cost_remaining', 2), ('observations_remaining', 0)]:
            case = self.case(); case['initial']['budget'][field] = amount
            broker = Broker(case)
            self.assertNotIn('c02_call_flags', [c['check_id'] for c in broker.view()['checks']])

    def test_partial_bundle_and_incompatible_reveal_are_atomic(self):
        partial = self.case(); partial['outcomes']['c02_call_flags']['facts'].pop()
        incompatible = self.case(); e = incompatible['initial']; f = copy.deepcopy(e['facts'][0])
        f.update(id=2, input_id=2, predicate='exported', value={'kind': 'bool', 'value': True}); e['facts'].append(f)
        for case in [partial, incompatible]:
            broker = Broker(case); before = broker.view()
            with self.assertRaises(Invalid):
                broker.request('c02_call_flags')
            self.assertEqual(broker.view(), before)
            self.assertEqual(broker.totals(), {'attempts': 0, 'cost': 0, 'disclosed_facts': 0})

    def test_receiver_shape_cannot_be_taken_from_different_kind(self):
        case = self.case(4); e = case['initial']; f = copy.deepcopy(e['facts'][0])
        f.update(id=2, input_id=2, predicate='receiver_kind', value={'kind': 'receiver_kind', 'value': 'query_result'})
        e['facts'].append(f); broker = Broker(case)
        with self.assertRaisesRegex(Invalid, 'foreign_receiver_shape'):
            broker.request('c11_receiver_shape')
        self.assertEqual(broker.totals()['attempts'], 0)

    def test_timeout_is_an_attempt_with_cost_not_a_negative_fact(self):
        broker = Broker(self.case(11)); before = len(broker.view()['envelope']['facts'])
        receipt = broker.request('c02_call_flags')
        self.assertEqual(receipt['status'], 'timeout'); self.assertEqual(receipt['cost'], 3)
        self.assertEqual(receipt['disclosed_facts'], 0)
        self.assertEqual(len(broker.view()['envelope']['facts']), before)

    def test_fact_limit_failure_does_not_partially_commit(self):
        case = self.case(); anchor = case['initial']['facts'][0]
        case['initial']['facts'] = [dict(copy.deepcopy(anchor), id=i, input_id=i) for i in range(1, 129)]
        broker = Broker(case); before = broker.view()
        with self.assertRaisesRegex(Invalid, 'fact_limit'):
            broker.request('c01_call_copy')
        self.assertEqual(broker.view(), before); self.assertEqual(broker.totals()['attempts'], 0)

    def test_new_revision_invalidates_facts_without_refunding_attempts(self):
        broker = Broker(self.case(7)); broker.request('c01_call_copy')
        old = broker.view()['envelope']; new_scope = dict(old['scope'], revision_id=2)
        anchor = copy.deepcopy(old['facts'][0]); anchor.update(id=100, input_id=100, scope=new_scope, sequence=3)
        broker.advance_scope(new_scope, [anchor])
        self.assertNotIn('exported', active(broker.view()['envelope']))
        self.assertEqual(broker.view()['envelope']['budget']['observations_remaining'], 2)
        broker.request('c01_call_copy'); broker.request('c02_call_flags')
        self.assertEqual(broker.totals()['attempts'], 3)
        self.assertEqual(broker.view()['envelope']['budget']['observations_remaining'], 0)

    def test_failed_revision_admission_keeps_original_ledger(self):
        broker = Broker(self.case()); before = broker.view()
        bad = copy.deepcopy(before['envelope']['facts'][0])
        bad['scope']['revision_id'] = 2
        with self.assertRaisesRegex(Invalid, 'reused_fact_id'):
            broker.advance_scope(bad['scope'], [bad])
        self.assertEqual(broker.view(), before)

    def test_scope_A_B_A_never_resurrects_retired_facts_and_keeps_check_origin(self):
        broker = Broker(self.case(14)); broker.request('c02_call_flags')
        a = broker.view()['envelope']['scope']
        original = copy.deepcopy(broker.view()['envelope']['facts'])
        broker.advance_scope(dict(a, session_id=9), [])
        broker.advance_scope(a, [])
        self.assertEqual(broker.view()['envelope']['facts'], [])
        self.assertEqual(findings(broker.view()['envelope'])[0], {})
        self.assertEqual(broker.history()[0]['facts'], original)
        self.assertEqual(broker.history()[0]['facts'][-1]['check_id'], 'c02_call_flags')
        self.assertEqual(broker.totals()['attempts'], 1)

    def test_foreign_revision_unverified_identity_and_undefined_are_not_absence(self):
        for ident in [5, 9, 10]:
            record = episode(self.case(ident), FixedOrder())
            score = audit(self.case(ident), record)
            self.assertTrue(score['safe']); self.assertEqual(score['false_causes'], 0)
            self.assertEqual(record['events'][-1]['action']['supported'], [])

    def test_evaluator_detects_invented_cause_and_unsupported_correct_guess(self):
        class Guesser(FixedOrder):
            def decide(self, view):
                return terminal('diagnosis', 'bounded_finding', ['method_not_exported'], evidence=[1]), 0, {}
        for ident, field in [(1, 'unjustified_findings'), (2, 'false_causes')]:
            case = self.case(ident); score = audit(case, episode(case, Guesser()))
            self.assertFalse(score['safe']); self.assertGreater(score[field], 0)

    def test_evaluator_rejects_tampered_reveal_scope_budget_and_receipt(self):
        case = self.case(); original = episode(case, FixedOrder())
        mutations = []
        value = copy.deepcopy(original); value['events'][0]['outcome']['facts'][0]['value']['value'] = False; mutations.append(value)
        value = copy.deepcopy(original); value['events'][0]['after']['budget']['observations_remaining'] = 3; mutations.append(value)
        value = copy.deepcopy(original); value['events'][1]['outcome']['facts'].pop(); mutations.append(value)
        value = copy.deepcopy(original); value['events'][0]['receipt']['cost_total'] = 0; mutations.append(value)
        value = copy.deepcopy(original); value['events'][0]['after']['facts'][-1]['scope']['session_id'] = 99; mutations.append(value)
        value = copy.deepcopy(original); value['events'] = value['events'][:-1]; mutations.append(value)
        for value in mutations:
            with self.subTest(value=value['case_id']), self.assertRaises(Invalid):
                audit(case, value)

    def test_schedule_consumes_criteria_and_refuses_missing_or_duplicate_cases(self):
        result = report(self.manifest, self.cases, {'fixed': FixedOrder})
        criteria, digest = result['criteria'], result['criteria_sha256']
        for records in [result['records'][:-1], result['records'] + [result['records'][0]]]:
            with self.assertRaisesRegex(Invalid, 'incomplete_schedule'):
                audit_schedule(self.cases, ['fixed'], records, criteria, digest)
        mutated = dict(criteria, max_false_causes=1)
        with self.assertRaisesRegex(Invalid, 'criteria_changed'):
            audit_schedule(self.cases, ['fixed'], result['records'], mutated, digest)

    def test_bad_policy_protocol_is_failure_not_a_skipped_success(self):
        class Bad(FixedOrder):
            name = 'fixed'
            def decide(self, view): return {'kind': 'check', 'check_id': 'run_shell'}, 0, {}
        result = report(self.manifest, [self.case()], {'fixed': Bad})
        self.assertEqual(result['execution_status'], 'failed'); self.assertFalse(result['mechanical_safety_passed'])

    def test_no_native_or_competence_claim_from_green_development_controls(self):
        result = report(self.manifest, self.cases, {'fixed': FixedOrder, 'one_pass': OnePass})
        self.assertTrue(result['mechanical_safety_passed']); self.assertTrue(result['evaluation']['thresholds_consumed'])
        for key in ['native_acceptance', 'heldout_independence', 'ai_competence_accepted']:
            self.assertFalse(result[key])

    def test_one_shot_evaluator_independently_refuses_an_observation_trajectory(self):
        record = episode(self.case(), FixedOrder())
        self.assertGreater(len(record['events']), 1)
        record['policy'] = 'model_one_shot'
        with self.assertRaisesRegex(Invalid, 'one_shot_terminal_required'):
            audit(self.case(), record)

    def test_before_after_summary_keeps_exact_revisions_and_observed_claims(self):
        result = report(self.manifest, self.cases, {'fixed': FixedOrder})
        pair, = result['evaluation']['paired_revisions']
        self.assertEqual(pair['scope'], 'author_declared_development_control')
        self.assertEqual(pair['before']['revision_id'], 1)
        self.assertEqual(pair['after']['revision_id'], 2)
        self.assertEqual(pair['before']['supported'], ['method_not_exported'])
        self.assertEqual(pair['after']['supported'], [])
        self.assertIn('method_not_exported', pair['after']['refuted'])

    def test_ready_adapter_refuses_external_endpoints_and_invalid_model(self):
        for endpoint in ['https://example.org', 'http://localhost:11434', 'http://127.0.0.1:11434/path', 'http://user@127.0.0.1:11434']:
            with self.assertRaises(Invalid): ReadyAgent('model', endpoint)
        with self.assertRaises(Invalid): ReadyAgent('model\ncommand')

    def test_ready_failure_diagnostics_never_reflect_model_or_exception_text(self):
        secret = 'private model text / sensitive path'
        self.assertEqual(failure_detail(AttributeError(secret)), {'failure_class': 'AttributeError'})
        self.assertEqual(failure_detail(Invalid(secret)), {'failure_class': 'Invalid', 'failure_code': 'other_contract_failure'})
        self.assertEqual(failure_detail(Invalid('invalid_enum')), {'failure_class': 'Invalid', 'failure_code': 'invalid_enum'})

    def test_changed_implementation_during_run_cannot_write_pinned_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'result.json'
            with patch('diagnostic_pilot.run.source_hashes', side_effect=[{'run.py': 'before'}, {'run.py': 'after'}]):
                with self.assertRaisesRegex(Invalid, 'implementation_changed_during_run'):
                    main(['--policies', 'fixed', '--case-id', '1', '--output', str(output)])
            self.assertFalse(output.exists())

    def test_missing_ready_dependencies_or_model_are_explicitly_inconclusive(self):
        # Fresh standard-library interpreter has no optional model stack. If a
        # developer installed it, the deliberately unused local port is refused.
        result = report(self.manifest, [self.case()], {'ready_agent': lambda: ReadyAgent('uninstalled-model', 'http://127.0.0.1:1', timeout=10)})
        self.assertEqual(result['execution_status'], 'inconclusive')
        self.assertFalse(result['mechanical_safety_passed'])
        self.assertFalse(result['evaluation']['mechanical_safety_passed'])
        self.assertTrue(result['ledger_and_findings_safe'])
        self.assertEqual(result['scores'][0]['terminal_kind'], 'unavailable')
        self.assertFalse(result['ai_competence_accepted'])


if __name__ == '__main__':
    unittest.main()
