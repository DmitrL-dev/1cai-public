"""Incomplete WMI observations never become admitted native process evidence."""
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.test_stock_git_scm_lifecycle import api


def row(**changes):
    return {"ProcessId":77,"ParentProcessId":17,"ExecutablePath":"C:/owned/java.exe",
            "CommandLine":"java --owned",**changes}


def fixture(tmp_path,monkeypatch,snapshots,*,outcome=None,sequence=0,budget=None):
    module=api();state={"enabled":False,"captures":[],"saved":[],"events":[],"bounds":[]}
    remaining=iter(snapshots)
    @contextmanager
    def privilege():
        assert state["enabled"] is False
        state["enabled"]=True
        try:yield
        finally:state["enabled"]=False
    def require(ok,message):
        if not ok:raise RuntimeError(message)
    def bounded(seconds):
        state["bounds"].append(seconds)
        if budget:raise RuntimeError("global exercise budget exhausted")
        return seconds
    def capture(command,environment,output,label,**options):
        assert state["enabled"] is True
        state["captures"].append((label,options))
        return {"exit_code":0,"child_reaped":True,"timed_out":False,
                "output_limit_exceeded":False,"process_error":None,**(outcome or {})}
    probe=SimpleNamespace(capture=capture,_raw=lambda *_:json.dumps(next(remaining)).encode())
    worker=SimpleNamespace(Acceptance=object,require=require,bounded=bounded,
        save=lambda path,value:state["saved"].append(path.name))
    native=SimpleNamespace(debug_privilege=privilege,
        privileges=lambda:[{"name":"SeDebugPrivilege","enabled":state["enabled"]}])
    cls=module.acceptance_type(worker,None,probe,None,None,None,None);test=cls.__new__(cls)
    test.native,test.output,test.query_sequence=native,tmp_path,sequence
    test.event=lambda name,**fields:state["events"].append((name,fields))
    monkeypatch.setattr(module.shutil,"which",lambda _:str(tmp_path/"pwsh.exe"))
    return test,state


@pytest.mark.parametrize("field,value",[("ExecutablePath",None),("ExecutablePath",""),
    ("CommandLine",None),("CommandLine","")])
def test_unavailable_row_requeries_whole_snapshot_and_admits_only_complete_rows(tmp_path,monkeypatch,field,value):
    complete=[row(),row(ProcessId=78,ParentProcessId=77)]
    test,state=fixture(tmp_path,monkeypatch,[[row(**{field:value})],complete])
    assert test.processes()==complete and test.query_sequence==2
    assert [label for label,_ in state["captures"]]==["stock-processes-1","stock-processes-2"]
    assert state["saved"]==["stock-processes-1.json","stock-processes-2.json"]
    assert all(options=={"timeout":10} for _,options in state["captures"])
    assert state["enabled"] is False
    scopes=[fields for name,fields in state["events"] if name=="stock_debug_privilege_inspected"]
    assert len(scopes)==2 and all(s["privileges_restored"] is True for s in scopes)
    observed=[fields for name,fields in state["events"] if name=="stock_process_inventory_observed"]
    assert [(s["attempt"],s["complete"]) for s in observed]==[(1,False),(2,True)]
    retries=[fields for name,fields in state["events"] if name=="stock_process_inventory_retry"]
    assert retries==[{"label":"stock-processes-1","attempt":1,"next_attempt":2,"max_attempts":3}]


def test_third_complete_observation_stays_inside_final_privilege_scope(tmp_path,monkeypatch):
    test,state=fixture(tmp_path,monkeypatch,[[row(ExecutablePath=None)],[row(CommandLine=None)],[row()]])
    with test.process_inspection() as rows:
        assert rows==[row()] and state["enabled"] is True
        assert len(state["captures"])==3
    assert state["enabled"] is False
    assert len([e for e in state["events"] if e[0]=="stock_debug_privilege_inspected"])==3


@pytest.mark.parametrize("field,value",[("ExecutablePath",None),("ExecutablePath",""),
    ("CommandLine",None),("CommandLine","")])
def test_persistently_unavailable_descendant_refuses_after_three_retained_attempts(tmp_path,monkeypatch,field,value):
    test,state=fixture(tmp_path,monkeypatch,[[row(**{field:value})]]*3)
    with pytest.raises(RuntimeError,match="Native process inventory is incomplete"):test.processes()
    assert len(state["captures"])==len(state["saved"])==3 and state["enabled"] is False
    assert len([e for e in state["events"] if e[0]=="stock_process_inventory_retry"])==2


@pytest.mark.parametrize("rows",[{},[row()]*101,[{}],[row(ProcessId=True)],[row(ProcessId=0)],
    [row(ParentProcessId=True)],[row(ParentProcessId=-1)],[row(ExecutablePath=[])],
    [row(CommandLine=1)],[row(),row()]])
def test_malformed_inventory_is_fatal_without_retry(tmp_path,monkeypatch,rows):
    test,state=fixture(tmp_path,monkeypatch,[rows])
    with pytest.raises(RuntimeError,match="Native process inventory shape differs"):test.processes()
    assert len(state["captures"])==len(state["saved"])==1 and state["enabled"] is False
    assert not any(name=="stock_process_inventory_retry" for name,_ in state["events"])


@pytest.mark.parametrize("outcome",[{"exit_code":1},{"timed_out":True},{"child_reaped":False},
    {"output_limit_exceeded":True},{"process_error":"IncompletePipeCapture"}])
def test_failed_capture_is_fatal_without_completeness_retry(tmp_path,monkeypatch,outcome):
    test,state=fixture(tmp_path,monkeypatch,[],outcome=outcome)
    with pytest.raises(RuntimeError,match="Native process inventory failed"):test.processes()
    assert len(state["captures"])==len(state["saved"])==1 and state["enabled"] is False
    assert not any(name=="stock_process_inventory_retry" for name,_ in state["events"])


def test_empty_complete_inventory_is_returned_without_retry(tmp_path,monkeypatch):
    test,state=fixture(tmp_path,monkeypatch,[[]])
    assert test.processes()==[] and len(state["captures"])==1 and state["enabled"] is False


def test_retry_cannot_exceed_global_200_query_bound(tmp_path,monkeypatch):
    test,state=fixture(tmp_path,monkeypatch,[[row(ExecutablePath=None)]],sequence=199)
    with pytest.raises(RuntimeError,match="observations exceed bound"):test.processes()
    assert len(state["captures"])==1 and state["enabled"] is False


def test_exhausted_exercise_budget_prevents_starting_capture(tmp_path,monkeypatch):
    test,state=fixture(tmp_path,monkeypatch,[],budget=True)
    with pytest.raises(RuntimeError,match="exercise budget exhausted"):test.processes()
    assert not state["captures"] and state["enabled"] is False


def test_consumer_failure_restores_final_scope_without_another_attempt(tmp_path,monkeypatch):
    test,state=fixture(tmp_path,monkeypatch,[[row()]])
    with pytest.raises(ValueError,match="native image binding failed"):
        with test.process_inspection() as rows:
            assert rows==[row()] and state["enabled"] is True
            raise ValueError("native image binding failed")
    assert state["enabled"] is False and len(state["captures"])==1
