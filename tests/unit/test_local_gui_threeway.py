"""Real ZIP/HTTP three-role inventory, lifecycle, resource and disclosure tests."""
import hashlib
import http.client
import json
import sys
import threading
import time
from urllib.parse import urlencode

import pytest
from rentgen_core import gui, gui_threeway
from rentgen_core.errors import CoreError
from test_local_gui import running, upload, post, request, prepare, wait as import_wait
from test_rust_input_workflow import binary, zip_bytes
from test_metadata_three_way_materialize import PATH, xml

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux GUI qualification')


def current(server):
    job,outcome=upload(server,zip_bytes({PATH:xml(),'own.bsl':b'current','same.bsl':b'new','clash.bsl':b'current'}))
    assert outcome['status']=='ready',outcome
    return {'job':job,'input_sha256':outcome['result']['input']['input_sha256']}


def start(server,binding):
    status,value=post(server,'/api/threeway-start',binding)
    assert status==201,value
    assert value['job']==binding['job'] and value['current_sha256']==binding['input_sha256']
    return value


def status(server,plan):
    code,raw,_=request(server,'/api/threeway?'+urlencode({'plan':plan}))
    return code,json.loads(raw)


def wait_role(app,server,plan,role):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        code,value=status(server,plan)
        assert code==200,value
        if value['status'] != 'analyzing' and value['roles'][role]['status'] not in {'awaiting_upload','uploading','analyzing'}:
            if app.threeway_worker: app.threeway_worker.join(5)
            return value
        time.sleep(.01)
    pytest.fail('role did not finish')


def side(app,server,plan,role,files):
    code,reserved=post(server,'/api/threeway-upload-start',{'plan':plan,'role':role,'filename':role+'.zip'})
    assert code==201,reserved
    raw=files if isinstance(files,bytes) else zip_bytes(files)
    code,reply,_=request(server,'/api/threeway-upload?'+urlencode({'plan':plan,'upload':reserved['upload']}),'PUT',raw,{'Content-Type':'application/zip'})
    assert code==202,reply
    result=wait_role(app,server,plan,role)
    assert result['roles'][role]['sha256']==hashlib.sha256(raw).hexdigest()
    return result


def ready(app,server):
    binding=current(server);plan=start(server,binding)['plan']
    base={PATH:xml(),'own.bsl':b'old','same.bsl':b'old','clash.bsl':b'old','deleted.bsl':b'x'}
    upstream={PATH:xml(),'own.bsl':b'old','same.bsl':b'new','clash.bsl':b'upstream','added.bsl':b'x'}
    assert side(app,server,plan,'base',base)['status']=='awaiting_inputs'
    result=side(app,server,plan,'upstream',upstream)
    assert result['status']=='ready',result
    return binding,result


def page(server,result,offset=0,action='all'):
    q={'plan':result['plan'],'current_sha256':result['current_sha256'],'base_sha256':result['roles']['base']['sha256'],
       'upstream_sha256':result['roles']['upstream']['sha256'],'offset':offset,'action':action}
    code,raw,_=request(server,'/api/threeway-page?'+urlencode(q))
    return code,json.loads(raw)


def test_real_three_roles_classification_provenance_and_recovery(running):
    app,server,_=running
    binding,result=ready(app,server)
    assert result['coverage']['complete'] and result['coverage']['scope']=='exact_path_inventory'
    code,value=page(server,result)
    assert code==200,value
    assert {r['path']:r['action'] for r in value['rows']}=={PATH:'unchanged','own.bsl':'keep_current','same.bsl':'same_change','clash.bsl':'conflict','deleted.bsl':'same_change','added.bsl':'take_upstream'}
    deleted=next(r for r in value['rows'] if r['path']=='deleted.bsl')
    assert deleted['base'] and deleted['current'] is None and deleted['upstream'] is None
    code,raw,_=request(server,'/api/threeway-current?'+urlencode(binding))
    assert code==200 and json.loads(raw)==result
    assert app.current.id==binding['job']


def test_replacement_invalidates_old_hash_page_and_reuses_reserved_path(running):
    app,server,_=running
    _,result=ready(app,server)
    path=app.threeway.roles['upstream'].path
    old_page=page(server,result)[1]
    code,reserved=post(server,'/api/threeway-upload-start',{'plan':result['plan'],'role':'upstream','filename':'new.zip'})
    assert code==201 and app.threeway.roles['upstream'].path==path and not path.exists()
    assert page(server,result)[0]==400
    with pytest.raises(CoreError): app.validate_threeway_page(old_page)
    assert status(server,result['plan'])[1]['status']=='awaiting_inputs'
    assert post(server,'/api/threeway-upload-start',{'plan':result['plan'],'role':'base','filename':'other.zip'})[0]==409


@pytest.mark.parametrize('bad', [{'role':'current'},{'role':'BASE'},{'filename':'../bad.zip'},{'plan':'0'*32}])
def test_invalid_role_selector_does_not_allocate(running,bad):
    app,server,_=running
    plan=start(server,current(server))['plan']
    code,_=post(server,'/api/threeway-upload-start',{'plan':plan,'role':'base','filename':'base.zip',**bad})
    assert code==400 and not any(role.path.exists() for role in app.threeway.roles.values())


def test_cancel_ready_clears_rows_files_and_stale_pages(running):
    app,server,_=running
    _,result=ready(app,server)
    assert post(server,'/api/threeway-cancel',{'plan':result['plan']})[0]==200
    assert status(server,result['plan'])[1]['status']=='cancelled'
    assert page(server,result)[0]==400 and app.threeway.rows==()
    assert not any(role.path.exists() for role in app.threeway.roles.values())


def test_new_primary_invalidates_all_threeway_disclosure(running):
    app,server,_=running
    _,result=ready(app,server)
    prepare(server)
    assert status(server,result['plan'])[0]==400 and page(server,result)[0]==400
    assert not any(role.path.exists() for role in app.threeway.roles.values())


@pytest.mark.parametrize('mutation',['permission','current_hash','role_hash','cancel','page'])
def test_page_revalidated_after_json_serialization(running,monkeypatch,mutation):
    app,server,_=running
    _,result=ready(app,server);ctx=app.config.context();original=gui.json.dumps;changed=[]
    def dumps(value,*args,**kwargs):
        raw=original(value,*args,**kwargs)
        if isinstance(value,dict) and 'rows' in value and value.get('plan')==result['plan'] and not changed:
            changed.append(True)
            if mutation=='permission':
                with ctx.state.transaction(ctx.principal,write=True) as tx: tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
            elif mutation=='current_hash': app.current.sha256='0'*64
            elif mutation=='role_hash': app.threeway.roles['base'].sha256='0'*64
            elif mutation=='cancel': app.cancel_threeway(result['plan'])
            else: app.threeway.page='0'*32
        return raw
    monkeypatch.setattr(gui.json,'dumps',dumps)
    code,value=page(server,result)
    assert changed and code==(403 if mutation=='permission' else 400) and 'rows' not in value


def test_ready_status_cancelled_during_serialization_is_not_disclosed(running,monkeypatch):
    app,server,_=running
    _,result=ready(app,server);original=gui.json.dumps;changed=[]
    def dumps(value,*args,**kwargs):
        raw=original(value,*args,**kwargs)
        if isinstance(value,dict) and value.get('plan')==result['plan'] and value.get('status')=='ready' and not changed:
            changed.append(True);app.cancel_threeway(result['plan'])
        return raw
    monkeypatch.setattr(gui.json,'dumps',dumps)
    assert status(server,result['plan'])[0]==400


def test_active_body_prevents_slot_reuse_until_handler_finishes(running):
    app,server,_=running
    binding=current(server);plan=start(server,binding)['plan']
    code,res=post(server,'/api/threeway-upload-start',{'plan':plan,'role':'base','filename':'base.zip'})
    assert code==201
    role=app.threeway.roles['base'];raw=zip_bytes({'safe.bsl':b'base'})
    con=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    con.putrequest('PUT','/api/threeway-upload?'+urlencode({'plan':plan,'upload':res['upload']}))
    for k,v in {'Origin':server.origin,'X-Rentgen-Session':app.token,'Content-Type':'application/zip','Content-Length':str(len(raw))}.items():con.putheader(k,v)
    con.endheaders();con.send(raw[:10])
    deadline=time.monotonic()+3
    while not role.handler_active and time.monotonic()<deadline:time.sleep(.005)
    assert role.handler_active
    try:
        assert post(server,'/api/threeway-start',binding)[0]==409
        assert role.handler_active and app.threeway.cancel.is_set()
        con.send(raw[10:]);reply=con.getresponse();reply.read();assert reply.status==400
    finally:con.close()
    deadline=time.monotonic()+3
    while role.handler_active and time.monotonic()<deadline:time.sleep(.005)
    assert not role.handler_active and not role.path.exists()
    assert start(server,binding)['plan']!=plan


def test_six_full_slots_are_reserved_before_bodies(running):
    app,server,root=running
    start(server,current(server))
    # Account for independent already-bounded primary/comparison reservations.
    # These owned temporary stand-ins model current+pending slots without writes.
    from types import SimpleNamespace
    app.pending=SimpleNamespace(path=root/'pending.zip')
    app.comparison_current=SimpleNamespace(path=root/'comparison-current.zip')
    app.comparison_pending=SimpleNamespace(path=root/'comparison-pending.zip')
    try:
        assert len(app._zip_slots())==6
        app._reserve_zip_slots(0)
        with pytest.raises(CoreError) as error: app._reserve_zip_slots(1)
        assert error.value.code=='GUI_RESOURCE_LIMIT'
        assert not any(p.exists() for p in (app.pending.path,app.comparison_current.path,app.comparison_pending.path))
    finally:
        app.pending=app.current;app.comparison_current=app.comparison_pending=None


def test_empty_base_and_manifest_only_inputs_are_supported(running):
    app,server,_=running
    plan=start(server,current(server))['plan']
    assert side(app,server,plan,'base',{})['status']=='awaiting_inputs'
    result=side(app,server,plan,'upstream',{'plain.txt':b'not XML'})
    assert result['status']=='ready',result
    assert result['coverage']['side_entries']['base']==0
    assert page(server,result)[0]==200


@pytest.mark.parametrize('base,upstream', [({'Dir/a.bsl':b'a'},{'dir/b.bsl':b'b'}),({'a':b'a'},{'a/b':b'b'}),({'É.bsl':b'a'},{'E\u0301.bsl':b'b'})],ids=['directory-case','file-parent','unicode-alias'])
def test_late_cross_role_collisions_fail_whole_plan(running,base,upstream):
    app,server,_=running
    plan=start(server,current(server))['plan']
    side(app,server,plan,'base',base)
    result=side(app,server,plan,'upstream',upstream)
    assert result['status']=='error' and 'counts' not in result and app.threeway.rows==()


def test_prior_role_is_rehashed_before_final_inventory(running):
    app,server,_=running
    plan=start(server,current(server))['plan']
    side(app,server,plan,'base',{'base.bsl':b'base'})
    app.threeway.roles['base'].path.write_bytes(zip_bytes({'base.bsl':b'changed'}))
    result=side(app,server,plan,'upstream',{'up.bsl':b'up'})
    assert result['status']=='error' and 'counts' not in result and app.threeway.rows==()


def test_expired_reservation_is_visible_and_retryable(running):
    app,server,_=running
    plan=start(server,current(server))['plan']
    assert post(server,'/api/threeway-upload-start',{'plan':plan,'role':'base','filename':'base.zip'})[0]==201
    app.threeway.roles['base'].created_at-=31
    result=status(server,plan)[1]
    assert result['status']=='error' and result['error']=='UPLOAD_TIMEOUT'
    assert side(app,server,plan,'base',{'a':b'a'})['status']=='awaiting_inputs'


@pytest.mark.parametrize('action',['cancel','revoke','close'])
def test_actual_rust_child_is_reaped_on_interruption(running,monkeypatch,action):
    app,server,_=running
    plan=start(server,current(server))['plan'];ctx=app.config.context()
    entered,proceed,children=threading.Event(),threading.Event(),[]
    original=gui_threeway.RustInputSession.open_import
    def opened(session,*args):
        result=original(session,*args)
        if threading.current_thread().name=='rentgen-gui-threeway':
            children.append(session.process);entered.set();assert proceed.wait(5)
        return result
    monkeypatch.setattr(gui_threeway.RustInputSession,'open_import',opened)
    code,res=post(server,'/api/threeway-upload-start',{'plan':plan,'role':'base','filename':'base.zip'})
    assert code==201
    assert request(server,'/api/threeway-upload?'+urlencode({'plan':plan,'upload':res['upload']}),'PUT',zip_bytes({'a':b'a'}),{'Content-Type':'application/zip'})[0]==202
    assert entered.wait(5)
    try:
        if action=='cancel': assert post(server,'/api/threeway-cancel',{'plan':plan})[0]==200
        elif action=='close': app.begin_close()
        else:
            with ctx.state.transaction(ctx.principal,write=True) as tx:tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
    finally:proceed.set()
    app.threeway_worker.join(5)
    assert not app.threeway_worker.is_alive() and children and all(p.poll() is not None for p in children)
    assert app.threeway.status in {'cancelled','error'} and app.threeway.rows==()


def test_real_existing_slots_coexist_without_extra_role_copy(running):
    from test_local_gui_comparison import submit
    app,server,_=running
    job,outcome=upload(server,zip_bytes({PATH:xml()}))
    assert submit(app,server,job,outcome,zip_bytes({PATH:xml()}))[1]['status']=='ready'
    assert submit(app,server,job,outcome,b'bad zip')[1]['status']=='error'
    failed=prepare(server)
    assert request(server,'/api/import?job='+failed,'PUT',b'bad zip',{'Content-Type':'application/zip'})[0]==202
    assert import_wait(server,failed)['status']=='error';app.worker.join(5)
    result=start(server,{'job':job,'input_sha256':outcome['result']['input']['input_sha256']})
    assert len(app._zip_slots())==6
    assert side(app,server,result['plan'],'base',{'a':b'a'})['status']=='awaiting_inputs'
    old=app.threeway.roles['base'].path
    assert side(app,server,result['plan'],'base',{'b':b'b'})['status']=='awaiting_inputs'
    assert app.threeway.roles['base'].path==old and len(app._zip_slots())==6
    assert len(list(__import__('pathlib').Path(app.temp.name).glob('*.zip')))<=6
