"""Real stock composition/Git/SQLite/Go; BSL output injected, no native SCM."""
from dataclasses import replace
import importlib.util
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from rentgen_core import service_entry
from rentgen_core.git_observer import observe_git
import test_git_service_trust as fixtures

configured,scanner=fixtures.configured,fixtures.scanner
project,workspace=fixtures.project,fixtures.workspace
pytestmark=fixtures.pytestmark


def load(name):
    path=Path(__file__).resolve().parents[2]/'scripts/verification'/name
    spec=importlib.util.spec_from_file_location('actual_publication_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_coordinator_reads_real_stock_publications_for_two_commits_and_repeat(configured,workspace,monkeypatch,scanner):
    observer,source,module,_,adapter=fixtures.wire(configured,workspace,monkeypatch,scanner,3)
    config=replace(service_entry.load_config(configured.path),max_cycles=1)
    lifecycle=load('scm_stock_git_lifecycle.py');measurement=load('scm_stock_git_measurement.py')
    import json,sqlite3
    from dataclasses import asdict
    from rentgen_core.context import Principal
    from rentgen_core.observer import Observer
    from project_access_test_support import grant_membership
    owner=observer.principal;service=Principal('windows-sid:S-1-5-19','local_os')
    with observer._context(write=True).state.transaction(owner,write=True) as tx:
        grant_membership(tx,service,{'project:read','analysis:run'})
    with sqlite3.connect(observer.database) as db:
        binding=json.loads(db.execute('SELECT binding FROM meta WHERE id=1').fetchone()[0])
        binding['principal']=asdict(service)
        db.execute('UPDATE meta SET binding=? WHERE id=1',(json.dumps(binding),))
    import rentgen_core.local_identity as identity
    monkeypatch.setattr(identity,'current_windows_principal',lambda:service)
    service_observer=Observer(observer.runtime,service,observer.project_id,observer.profile)
    observer=lifecycle.fixture_owner_profile(service_observer,owner)
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    cls=lifecycle.acceptance_type(SimpleNamespace(Acceptance=object,require=require),None,None,None,None,None,None)
    test=cls.__new__(cls);test.observer=observer;test.context=observer._context(write=True)
    test.f={'project_id':observer.project_id}
    from rentgen_core.git_watcher import NotificationOutbox
    test.outbox=NotificationOutbox(observer.profile/'git-outbox.json')
    commits=[];before=None
    for index in range(3):
        if index==1:
            module.write_bytes(module.read_bytes()+b'// owned new stock commit\n')
            fixtures.git(source,'add','.');fixtures.git(source,'commit','-m','Owned second stock commit')
        commit=observe_git(source).commit
        if commit not in commits: commits.append(commit)
        worker=service_entry.create_worker(config)
        try: assert worker.run(Event())==1
        finally: worker.close()
        doc=test.publication()
        from rentgen_diagnostics.git_bsl_analyzer import PROFILE_ID,SCOPE_ID
        report=doc['findings']['state']['report']
        assert report['profile_id']==PROFILE_ID and report['scope_id']==SCOPE_ID and report['complete'] is True
        assert report['observation']['repository']==str(source.resolve())
        assert report['observation']['commit']==commits[-1]
        proof=measurement.validate_publication(doc,project=observer.project_id,source=source,commits=commits)
        assert proof['findings_reports']==len(commits)
        if index==2: assert doc['findings']==before['findings'] and doc['outbox']==before['outbox'] and doc['owners']==before['owners']
        before=doc
    assert len(commits)==len(adapter.calls)==2


def test_fixture_owner_can_read_localservice_profile_after_service_membership_revocation(workspace,monkeypatch):
    import json,sqlite3
    import pytest
    from dataclasses import asdict
    from rentgen_core.context import Principal
    from rentgen_core.errors import CoreError
    from rentgen_core.observer import Observer
    from project_access_test_support import grant_membership
    observer,_,_=workspace;owner=observer.principal
    service=Principal('windows-sid:S-1-5-19','local_os')
    context=observer._context(write=True)
    with context.state.transaction(owner,write=True) as tx:
        grant_membership(tx,service,{'project:read','analysis:run'})
    service_observer=Observer(observer.runtime,service,observer.project_id,observer.profile)
    with sqlite3.connect(observer.database) as db:
        row=json.loads(db.execute('SELECT binding FROM meta WHERE id=1').fetchone()[0])
        row['principal']=asdict(service)
        db.execute('UPDATE meta SET binding=? WHERE id=1',(json.dumps(row),))
    with pytest.raises(CoreError) as error: observer.status()
    assert error.value.code=='OBSERVER_PROFILE_MISMATCH'
    lifecycle=load('scm_stock_git_lifecycle.py')
    view=lifecycle.fixture_owner_profile(service_observer,owner)
    assert view.status()['last_snapshot'] is None and view.findings_status()['state'] is None
    with context.state.transaction(owner,write=True) as tx:
        grant_membership(tx,service,{'project:read'})
    with pytest.raises(CoreError) as error: service_observer.findings_status()
    assert error.value.code=='PROJECT_FORBIDDEN'
    assert view.findings_status()['state'] is None
    with view.locked(): pass
    with sqlite3.connect(observer.database) as db:
        assert json.loads(db.execute('SELECT binding FROM meta WHERE id=1').fetchone()[0])==row
    operator=Principal('stock-fixture-other-admin','local_os')
    with context.state.transaction(owner,write=True) as tx:
        grant_membership(tx,operator,{'project:read','project:admin','analysis:run'})
    with context.state.transaction(operator,write=True) as tx:
        grant_membership(tx,owner,{'project:read'})
    with pytest.raises(CoreError) as error: view.findings_status()
    assert error.value.code=='PROJECT_FORBIDDEN'
