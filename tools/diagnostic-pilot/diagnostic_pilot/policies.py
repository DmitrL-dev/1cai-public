"""Actual bounded Rust/agent adapters and deterministic development baselines."""
import hashlib
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

from .broker import active
from .contracts import Invalid, action, bounded_json, encoded, integer, require
from .ready_worker import FAILURE_CLASSES, FAILURE_CODES, FAILURE_STAGES, RESPONSE_TYPES


def terminal(kind='abstain', reason='insufficient_data', supported=(), refuted=(), evidence=()):
    return {'kind': kind, 'reason': reason, 'supported': sorted(supported),
            'refuted': sorted(refuted), 'evidence_ids': sorted(set(evidence))}


def _baseline_states(view):
    """One-pass deterministic policy; does not import the evaluator/oracle."""
    e = view['envelope']; t = e['target']; facts = active(e)
    def get(key):
        pair = facts.get(key)
        return pair[0].get('present') if pair and key == 'member_present' else pair[0].get('value') if pair else None
    states = {}
    if e['access'] != 'usable' or e['cancelled'] or e['scope']['platform'] != 'synthetic_8_3_27' or e['scope']['compatibility'] != 'synthetic_v1' or e['scope']['execution'] == 'unknown':
        return states, []
    if t['kind'] == 'call':
        if get('call_edge') != 'static_external_resolved' or t['module_kind'] != 'common' or t['route'] == 'dynamic':
            return states, []
        # A conflicting dependency must suppress even another sufficient premise.
        by_pred = {}
        suppressed = {i for f in e['facts'] for i in f['supersedes']}
        for f in e['facts']:
            if f['id'] not in suppressed and f['scope'] == e['scope'] and f['target'] == t and f['adapter'] == 'synthetic_v1' and f['sequence'] <= e['sequence'] <= f['valid_until'] and f['state'] in {'observed', 'conflicting'}:
                by_pred.setdefault(f['predicate'], []).append(f)
        conflicts = {p for p, fs in by_pred.items() if any(f['state'] == 'conflicting' for f in fs) or len({encoded(f['value']) for f in fs}) > 1}
        gates = ['context_enabled', 'compiled_copy_present'] + (['server_call_enabled'] if t['route'] == 'server_bridge' else [])
        if t['route'] == 'server_bridge' and e['scope']['execution'] != 'thin_client':
            return states, []
        states['call_context_unavailable'] = 'unknown' if conflicts & set(gates) else 'supported' if any(get(p) is False for p in gates) else 'refuted' if all(get(p) is True for p in gates) else 'unknown'
        states['method_not_exported'] = 'supported' if get('exported') is False else 'refuted' if get('exported') is True else 'unknown'
    elif get('receiver_retained') is True:
        shape = facts.get('member_present', ({},))[0]
        present = shape.get('present') if shape.get('receiver_kind') == get('receiver_kind') else None
        if t['kind'] == 'receiver':
            states['receiver_kind_mismatch'] = 'unknown' if get('receiver_kind') is None else 'refuted' if get('receiver_kind') == t['expected_kind'] else 'supported'
            states['immediate_member_absent'] = 'supported' if present is False else 'refuted' if present is True else 'unknown'
        else:
            positive = get('receiver_kind') == 'application_object' and present is False and get('source_member') == 'present' and get('object_correlation') == 'same_attested'
            negative = get('receiver_kind') is not None and get('receiver_kind') != 'application_object' or present is True or get('source_member') == 'absent_complete' or get('object_correlation') == 'different_attested'
            states['source_runtime_mismatch'] = 'supported' if positive else 'refuted' if negative else 'unknown'
    evidence = [i for _, ids in facts.values() for i in ids]
    return states, evidence


class FixedOrder:
    name = 'fixed'
    def decide(self, view):
        states, evidence = _baseline_states(view)
        supported = [h for h, s in states.items() if s == 'supported']
        refuted = [h for h, s in states.items() if s == 'refuted']
        if supported:
            return terminal('diagnosis', 'bounded_finding', supported, refuted, evidence), 0, {}
        if states and len(refuted) == len(states):
            return terminal(reason='all_refuted', refuted=refuted, evidence=evidence), 0, {}
        ready = [c for c in view['checks'] if c['consent'] == 'ready']
        if ready:
            return {'kind': 'check', 'check_id': ready[0]['check_id']}, 0, {}
        return terminal(reason='pending_consent' if view['checks'] else 'budget_exhausted' if view['envelope']['budget']['observations_remaining'] == 0 else 'insufficient_data'), 0, {}
    def close(self):
        pass


class OnePass(FixedOrder):
    name = 'one_pass'
    def decide(self, view):
        result, charge, metrics = super().decide(view)
        return (terminal() if result['kind'] == 'check' else result), charge, metrics


def stop(child):
    if child.poll() is None:
        try:
            if os.name == 'posix':
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.kill()
        except ProcessLookupError:
            pass
    child.wait(timeout=5)


class RustPolicy:
    name = 'rust'
    def __init__(self, binary, digest, timeout=10):
        self.binary = Path(binary).resolve(strict=True)
        require(self.binary.is_file() and hashlib.sha256(self.binary.read_bytes()).hexdigest() == digest, 'rust_binary_hash')
        self.digest = digest; self.timeout = timeout
    def raw(self, view):
        require(hashlib.sha256(self.binary.read_bytes()).hexdigest() == self.digest, 'rust_binary_changed')
        require(len(encoded(view['envelope'])) <= 65536, 'rust_input_limit')
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            child = subprocess.Popen([str(self.binary)], stdin=subprocess.PIPE, stdout=output, stderr=errors,
                                     start_new_session=os.name == 'posix')
            try:
                child.stdin.write(encoded(view['envelope'])); child.stdin.close()
                deadline = time.monotonic() + self.timeout
                while child.poll() is None:
                    require(time.monotonic() < deadline, 'rust_timeout')
                    require(output.tell() <= 256 * 1024 and errors.tell() <= 65536, 'rust_output_limit')
                    time.sleep(.005)
                output.seek(0); errors.seek(0)
                raw = output.read(256 * 1024 + 1)
                require(child.returncode == 0 and not errors.read(65537), 'rust_process_failed')
                result = bounded_json(raw, 256 * 1024)
                require(result.get('assurance') == 'experimental_synthetic_not_authenticated', 'rust_assurance')
                require(hashlib.sha256(self.binary.read_bytes()).hexdigest() == self.digest, 'rust_binary_changed')
                return result
            finally:
                stop(child)
    def decide(self, view):
        result = self.raw(view)
        charge = result['rule_applications_used']; integer(charge, 0, 256)
        if result['kind'] == 'check_request' and result['stop'] != 'pending_consent':
            decision = {'kind': 'check', 'check_id': result['selected_check']['check_id']}
        else:
            supported = result['supported']
            refuted = [h['id'] for h in result['hypotheses'] if h['state'] == 'refuted']
            reason = 'bounded_finding' if supported else result['stop'] if result['stop'] in {'all_refuted', 'budget_exhausted', 'pending_consent', 'unsupported_scope', 'cancelled', 'access_revoked'} else 'insufficient_data'
            decision = terminal('diagnosis' if supported else 'abstain', reason, supported, refuted, result['trace']['contributing_ids'])
        return action(decision), charge, {'rust_calls': 1}
    def close(self):
        pass


class ReadyAgent:
    """Persistent real framework worker. Host retains the only evidence broker."""
    name = 'ready_agent'
    worker_script = 'ready_worker.py'
    def __init__(self, model, endpoint='http://127.0.0.1:11434', timeout=120, rust=None):
        require(type(model) is str and 1 <= len(model) <= 128 and not any(ord(c) < 33 for c in model), 'invalid_model')
        url = urlsplit(endpoint)
        require(url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port and not url.username and not url.password and not url.path and not url.query and not url.fragment, 'loopback_model_required')
        self.model, self.endpoint, self.timeout, self.rust = model, endpoint, timeout, rust
        if rust:
            self.name = 'hybrid'
        self.child = None; self._stderr = None; self._deadline = None
    def decide(self, view):
        if self.child is None:
            self._stderr = tempfile.TemporaryFile()
            env = {key: os.environ[key] for key in ['PATH', 'SYSTEMROOT', 'WINDIR', 'TMPDIR', 'TEMP', 'TMP'] if key in os.environ}
            self.child = subprocess.Popen([sys.executable, '-I', str(Path(__file__).with_name(self.worker_script)),
                '--model', self.model, '--endpoint', self.endpoint], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self._stderr, env=env, start_new_session=os.name == 'posix')
            self._deadline = time.monotonic() + self.timeout
        payload = dict(view)
        rule_charge = 0
        if self.rust is not None:
            payload['rust_advice'] = self.rust.raw(view)
            rule_charge = payload['rust_advice']['rule_applications_used']
            integer(rule_charge, 0, 256)
        frame = encoded(payload)
        require(len(frame) <= 65535, 'agent_input_limit')
        self.child.stdin.write(frame + b'\n'); self.child.stdin.flush()
        received = queue.Queue(maxsize=1)
        def read_line():
            try:
                received.put(self.child.stdout.readline(65537))
            except OSError:
                received.put(b'')
        thread = threading.Thread(target=read_line, daemon=True); thread.start()
        while True:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                stop(self.child); thread.join(timeout=2)
                raise Invalid('agent_deadline')
            require(self._stderr.tell() <= 65536, 'agent_stderr_limit')
            try:
                raw = received.get(timeout=min(.05, remaining)); break
            except queue.Empty:
                continue
        require(raw.endswith(b'\n') and len(raw) <= 65536, 'agent_protocol')
        require(self._stderr.tell() <= 65536, 'agent_stderr_limit')
        result = bounded_json(raw)
        metrics = result.pop('metrics', {})
        require(type(metrics) is dict and not set(metrics) - {'model_requests', 'input_tokens', 'output_tokens', 'wall_milliseconds', 'failure_stage', 'failure_class', 'failure_code', 'structured_response_type'}, 'invalid_metrics')
        for key, value in metrics.items():
            if key == 'failure_stage':
                require(type(value) is str and value in FAILURE_STAGES, 'invalid_metrics')
            elif key == 'failure_class':
                require(type(value) is str and value in FAILURE_CLASSES | {'other'}, 'invalid_metrics')
            elif key == 'failure_code':
                require(type(value) is str and value in FAILURE_CODES, 'invalid_metrics')
            elif key == 'structured_response_type':
                require(type(value) is str and value in RESPONSE_TYPES, 'invalid_metrics')
            else:
                require(value is None or type(value) is int and 0 <= value <= 10**9, 'invalid_metrics')
        if self.rust is not None:
            metrics['rust_calls'] = 1
        return action(result), rule_charge, metrics
    def close(self):
        if self.child:
            stop(self.child)
            self.child.stdin.close(); self.child.stdout.close(); self._stderr.close()


class ModelOneShot(ReadyAgent):
    """One terminal decision from initial evidence; a one-request ablation."""
    name = 'model_one_shot'
    worker_script = 'one_shot_worker.py'
    def __init__(self, model, endpoint='http://127.0.0.1:11434', timeout=120):
        super().__init__(model, endpoint, timeout)
        self._decided = False
    def decide(self, view):
        require(not self._decided, 'one_shot_already_decided')
        self._decided = True
        decision, charge, metrics = super().decide(view)
        require(decision['kind'] != 'check', 'one_shot_terminal_required')
        require(type(metrics.get('model_requests')) is int and 0 <= metrics['model_requests'] <= 1, 'invalid_metrics')
        if decision['kind'] != 'unavailable':
            require(metrics['model_requests'] == 1, 'invalid_metrics')
        return decision, charge, metrics
