"""Pure observer-ledger controls; examples are synthetic, never live evidence."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('rentgen_observer_analysis',ROOT/'tests/fixtures/source_facts/observer_fidelity/analyze.py')
analysis=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(analysis)

def info(pid=1,op=1,ret=80,nr=262):
 return f'RENTGEN_OBSERVER info pid={pid} entering=1 ret={ret} errno=0 op={op} retained_union_nr={nr} a0=100 a1=200\n'

def regs(pid=2,ret=0,nr=35):
 return f'RENTGEN_OBSERVER regs pid={pid} entering=1 ret={ret} errno=0 orig_rax={nr} rdi=400 rsi=500 rdx=0\n'

def test_genuine_fields_needed_for_none_reuse_and_fallback():
 summary=analysis.inspect_ledger(info()+info(pid=2,op=0,ret=24)+regs())
 assert summary['cross_pid_retained_union_count']==summary['successful_fallback_count']==summary['changed_syscall_number_count']==1

@pytest.mark.parametrize('text',[info()+regs(), info()+info(pid=2,op=1,ret=80)+regs(), info()+info(pid=2,op=0,ret=-1)+regs(), info()+info(pid=2,op=0,ret=23)+regs()])
def test_wrong_stop_or_short_failed_record_is_not_positive(text):
 summary=analysis.inspect_ledger(text);assert summary['cross_pid_retained_union_count']==summary['successful_fallback_count']==0

def test_same_pid_union_is_not_cross_pid_evidence():
 assert analysis.inspect_ledger(info()+info(op=0,ret=24))['cross_pid_retained_union_count']==0

@pytest.mark.parametrize('tail',[regs(pid=3),regs(ret=-1),'RENTGEN_OBSERVER wait pid=2 status=4991\n'+regs()])
def test_fallback_requires_adjacent_matching_success(tail):
 assert analysis.inspect_ledger(info()+info(pid=2,op=0,ret=24)+tail)['successful_fallback_count']==0

@pytest.mark.parametrize('bad',['RENTGEN_OBSERVER unknown pid=1\n','RENTGEN_OBSERVER wait pid=1\n','RENTGEN_OBSERVER wait pid=1 status=0 status=1\n','RENTGEN_OBSERVER wait pid=0 status=0\n','RENTGEN_OBSERVER wait pid=1 status=opaque\n'])
def test_malformed_ledger_rejected(bad):
 with pytest.raises(ValueError):analysis.records(bad)

def test_workflow_does_not_grant_privileges_or_rearm_original_trace():
 workflow=(ROOT/'.github/workflows/source-observer-ci.yml').read_text()
 assert '0f018fbee472e14e30584c9d03cfa0817e7c8081' in workflow
 assert 'github.run_attempt == 1' in workflow and 'persist-credentials: false' in workflow
 assert all(word not in workflow for word in ('sudo ','setcap ','sysctl ','CAP_SYS_PTRACE','pull_request_target'))
 original=(ROOT/'.github/workflows/source-facts-ci.yml').read_text()
 assert "github.event.before == '8cd77af51518da43560e48e10d08c3ec4f795acd'" in original


@pytest.mark.parametrize('prior',[info(op=0,ret=24),info(op=2,ret=33),info(op=1,ret=-1),info(op=1,ret=24),info(op=3,ret=80)])
def test_nonentry_or_incomplete_prior_is_not_reused_entry_evidence(prior):
 summary=analysis.inspect_ledger(prior+info(pid=2,op=0,ret=24)+regs())
 assert summary['cross_pid_retained_union_count']==summary['corrected_cross_pid_fallback_count']==0


def test_unchanged_fallback_is_reported_but_not_corrective_evidence():
 summary=analysis.inspect_ledger(info()+info(pid=2,op=0,ret=24)+regs(nr=262))
 assert summary['successful_fallback_count']==1 and summary['corrected_cross_pid_fallback_count']==0


def test_complete_seccomp_predecessor_supported():
 summary=analysis.inspect_ledger(info(op=3,ret=84)+info(pid=2,op=0,ret=24)+regs())
 assert summary['corrected_cross_pid_fallback_count']==1


RUNSPEC=importlib.util.spec_from_file_location('rentgen_observer_runner',ROOT/'tests/fixtures/source_facts/observer_fidelity/run_bounded.py')
runner=importlib.util.module_from_spec(RUNSPEC);RUNSPEC.loader.exec_module(runner)

class Child:
 pid=123
 def __init__(self, fail_wait=False):self.fail_wait=fail_wait;self.killed=False;self.waits=0
 def poll(self):return None
 def wait(self,timeout):
  self.waits+=1
  if self.fail_wait and self.waits==1:raise runner.subprocess.TimeoutExpired('owned',timeout)
  return 0
 def kill(self):self.killed=True


def no_children(*args):raise ChildProcessError()


def test_cleanup_handles_group_exit_race(monkeypatch):
 child=Child();seen=[]
 def gone(pid,sig):seen.append((pid,sig));raise ProcessLookupError()
 monkeypatch.setattr(runner.os,'killpg',gone);monkeypatch.setattr(runner.os,'waitpid',no_children)
 result=runner.cleanup_owned(child)
 assert result=={'cleanup_empty':True,'adopted_reaped':[],'cleanup_errors':[]}
 assert seen==[(123,runner.signal.SIGKILL)] and child.waits==1


def test_cleanup_records_wait_failure_and_reaps(monkeypatch):
 child=Child(fail_wait=True)
 monkeypatch.setattr(runner.os,'killpg',lambda *args:None);monkeypatch.setattr(runner.os,'waitpid',no_children)
 result=runner.cleanup_owned(child)
 assert child.killed and child.waits==2 and result['cleanup_empty']
 assert result['cleanup_errors']==['TimeoutExpired']


def test_partial_results_persist_before_next_attempt(tmp_path):
 rows=[{'version':'6.8','exit':1}];runner.write_results(tmp_path,rows)
 import json
 assert json.loads((tmp_path/'run-results.json').read_text())==rows
 assert not (tmp_path/'run-results.json.tmp').exists()


def test_stop_handler_does_not_interrupt_process_creation():
 old=runner.STOP_SIGNAL
 try:
  runner.stop_requested(runner.signal.SIGTERM,None)
  assert runner.STOP_SIGNAL==runner.signal.SIGTERM
 finally:runner.STOP_SIGNAL=old


def test_runner_parent_death_and_exception_cleanup_contract():
 source=(ROOT/'tests/fixtures/source_facts/observer_fidelity/run_bounded.py').read_text()
 assert 'libc.prctl(1,signal.SIGKILL' in source and 'os.getppid()!=parent' in source
 assert "'--kill-on-exit'" in source and 'finally:' in source
 assert 'cleanup=cleanup_owned(child)' in source and 'write_results(root,results)' in source
 assert "for sig in (signal.SIGTERM,signal.SIGINT)" in source
 assert "resource.RLIMIT_FSIZE,(32*1024*1024,32*1024*1024)" in source
