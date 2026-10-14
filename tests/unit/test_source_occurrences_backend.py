"""Occurrence API over real owned SQLite state and the verified Rust helper."""
import hashlib
import sys
import threading

import pytest

from rentgen_core import source_occurrences as occurrences
from rentgen_core.errors import CoreError
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import initialize_local_identity
from rentgen_core.registry import ProjectRegistry
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Actual Linux Rust submitted-byte contract')
TARGET = 'Modules/Selected.bsl'


@pytest.fixture
def owned(tmp_path, binary):
    principal = initialize_local_identity(tmp_path/'private'/'identity.json')
    source = tmp_path/'source'; source.mkdir()
    (source/'untouched.bsl').write_bytes(b'owned synthetic sentinel')
    registry = ProjectRegistry.create(tmp_path/'registry.sqlite3')
    project = registry.register(principal, source_root=source, state_root=tmp_path/'state', display_name='Occurrence test')
    ctx = LocalRuntime(registry.path).state_context(principal, project.project_id)
    def options(raw=b'needle', path=TARGET, extra=None):
        files={path:raw, **(extra or {})}
        archive=tmp_path/'input.zip'; archive.write_bytes(zip_bytes(files))
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        return dict(archive=archive,archive_sha256=digest,input_core=binary[0],input_core_sha256=binary[1],
                    reference={'input_sha256':digest,'relative_path':path,'raw_sha256':hashlib.sha256(raw).hexdigest()},query='needle')
    return ctx,options


def run(owned, raw=b'needle', **changes):
    ctx,options=owned
    return occurrences.search_source_occurrences(ctx,**{**options(raw),**changes})


def track_children(monkeypatch):
    children=[];original=occurrences.RustInputSession.open_import
    def opened(session,*a,**kw):
        result=original(session,*a,**kw);children.append(session.process);return result
    monkeypatch.setattr(occurrences.RustInputSession,'open_import',opened)
    return children


def test_real_bom_unicode_newlines_hashes_and_exact_contract(owned):
    raw='\ufeff😀needle\r\n\tneedle\rneedle\n'.encode()
    ctx,options=owned;args=options(raw);result=occurrences.search_source_occurrences(ctx,**args)
    assert result['input_ref']==args['reference']
    assert result['size_bytes']==len(raw) and result['query']=='needle' and result['analysis']=='literal_occurrences'
    assert result['conventions']=={'line_base':1,'column_base':1,'column_unit':'unicode_codepoint','newlines':'CRLF_CR_LF',
                                   'bom':'excluded','overlap':True,'case_sensitive':True,'normalization':'none'}
    assert result['coverage']=={'complete':True,'characters_scanned':len(raw.decode('utf-8-sig'))}
    assert [(r['line'],r['column'],r['offset']) for r in result['occurrences']]==[(1,2,1),(2,2,10),(3,1,17)]
    assert result['page']=={'offset':0,'limit':200,'total':3,'returned':3,'has_previous':False,'has_next':False}
    assert set(result)=={'input_ref','size_bytes','query','analysis','conventions','occurrences','coverage','page'}


@pytest.mark.parametrize('extension',['.bsl','.BSL','.os','.OS','.bsp'], ids=['bsl','bsl-upper','os','os-upper','bsp'])
def test_only_exact_selected_module_is_read(owned,monkeypatch,extension):
    ctx,options=owned;args=options(b'needle',path='Modules/code'+extension,extra={'Modules/Other.bsl':b'needle'*10})
    original=occurrences.RustInputSession.read_entry;paths=[]
    def read(session,entry):paths.append(entry['path']);return original(session,entry)
    monkeypatch.setattr(occurrences.RustInputSession,'read_entry',read)
    result=occurrences.search_source_occurrences(ctx,**args)
    assert result['page']['total']==1 and paths==[args['reference']['relative_path']]


def test_page_201_counts_full_inventory_and_rejects_beyond_total(owned):
    raw=b'needle\r\n'*201
    first=run(owned,raw)
    last=run(owned,raw,offset=200)
    assert len(first['occurrences'])==200 and first['page']['total']==201 and first['page']['has_next']
    assert last['page']=={'offset':200,'limit':200,'total':201,'returned':1,'has_previous':True,'has_next':False}
    assert last['occurrences'][0]['line']==201 and last['occurrences'][0]['offset']==1600
    with pytest.raises(CoreError) as error:run(owned,raw,offset=400)
    assert error.value.code=='INVALID_QUERY_OPTIONS'


@pytest.mark.parametrize('raw,query',[(b'', 'x'),(b'Needle','needle'),('e\u0301'.encode(),'é')], ids=['empty','case-sensitive','no-normalization'])
def test_complete_zero_results_are_valid_at_offset_zero(owned,raw,query):
    result=run(owned,raw,query=query)
    assert result['occurrences']==[] and result['page']['total']==0
    assert result['coverage']=={'complete':True,'characters_scanned':len(raw.decode('utf-8-sig'))}
    with pytest.raises(CoreError) as error:run(owned,raw,query=query,offset=200)
    assert error.value.code=='INVALID_QUERY_OPTIONS'


def test_maximum_source_dense_overlaps_and_last_aligned_page(owned):
    result=run(owned,b'a'*262144,query='a',offset=262000)
    assert result['page']=={'offset':262000,'limit':200,'total':262144,'returned':144,'has_previous':True,'has_next':False}
    assert result['occurrences'][-1]['offset']==262143 and result['occurrences'][-1]['column']==262144
    assert result['coverage']['characters_scanned']==262144
    assert run(owned,b'aaaa',query='aa')['page']['total']==3


@pytest.mark.parametrize('raw',[b'\xffneedle',b'\xff\xfeN\x00',b'needle\x00',b'a'*40000+b'\x0b',b'\xed\xa0\x80'], ids=['invalid-utf8','utf16','nul','late-control','encoded-surrogate'])
def test_encoding_and_late_control_failure_rejects_whole_result(owned,raw):
    with pytest.raises(CoreError) as error:run(owned,raw)
    assert error.value.code=='SOURCE_ENCODING_UNSUPPORTED'


def test_oversized_module_rejected_before_read_entry(owned,monkeypatch):
    ctx,options=owned;args=options(b'x'*262145)
    monkeypatch.setattr(occurrences.RustInputSession,'read_entry',lambda *a:pytest.fail('Oversized content must not be read'))
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='SOURCE_TOO_LARGE'


@pytest.mark.parametrize('change',[{'raw_sha256':'0'*64},{'relative_path':'Modules/Missing.bsl'},{'input_sha256':'0'*64}], ids=['raw-hash','missing-path','archive-hash'])
def test_stale_or_forged_reference_never_reads_selected_bytes(owned,monkeypatch,change):
    ctx,options=owned;args=options();args['reference']={**args['reference'],**change}
    monkeypatch.setattr(occurrences.RustInputSession,'read_entry',lambda *a:pytest.fail('Reference mismatch must not read bytes'))
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='SOURCE_NOT_AVAILABLE'


def test_second_call_reopens_and_rehashes_archive(owned):
    ctx,options=owned;args=options()
    assert occurrences.search_source_occurrences(ctx,**args)['page']['total']==1
    args['archive'].write_bytes(zip_bytes({TARGET:b'replacement'}))
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='IMPORT_HASH_MISMATCH'


def test_binary_hash_is_still_verified(owned):
    ctx,options=owned;args=options();args['input_core_sha256']='0'*64
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='INPUT_CORE_EXECUTABLE_INVALID'


@pytest.mark.parametrize('changes',[{'query':''},{'query':'x\ny'},{'query':'\ud800'},{'query':'я'*129},{'query':None},
                                    {'offset':True},{'offset':201},{'offset':262144},{'reference':{} }], ids=['empty-query','newline-query','surrogate-query','long-query','null-query','bool-offset','unaligned-offset','above-offset','empty-reference'])
def test_bad_inputs_fail_before_child_launch(owned,monkeypatch,changes):
    ctx,options=owned;args={**options(),**changes}
    monkeypatch.setattr(occurrences.RustInputSession,'__enter__',lambda *a:pytest.fail('Invalid input launched child'))
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code in {'INVALID_QUERY_OPTIONS','SOURCE_NOT_AVAILABLE'}


def test_denied_context_fails_before_argument_or_binary_access(owned,monkeypatch):
    ctx,options=owned;args=options()
    with ctx.state.transaction(ctx.principal,write=True) as tx:
        tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
    monkeypatch.setattr(occurrences.RustInputSession,'__enter__',lambda *a:pytest.fail('Denied operation launched child'))
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**{**args,'reference':None})
    assert error.value.code=='PROJECT_FORBIDDEN'


@pytest.mark.parametrize('ending',['cancel','project:read','analysis:run'], ids=['cancel','revoke-read','revoke-analysis'])
@pytest.mark.parametrize('query',['a','absent'], ids=['dense-hits','no-hits'])
def test_chunk_checkpoint_cancel_or_real_revocation_reaps_without_partial_result(owned,monkeypatch,ending,query):
    ctx,options=owned;args=options(b'a'*100000);args['query']=query
    children=track_children(monkeypatch);cancel=threading.Event();original=occurrences._scan;calls=[]
    def scan(text,query,offset,checkpoint):
        def at_chunk():
            calls.append(1)
            if len(calls)==2:
                if ending=='cancel':cancel.set()
                else:
                    with ctx.state.transaction(ctx.principal,write=True) as tx:
                        tx._connection.execute('DELETE FROM membership_permissions WHERE permission=?',(ending,))
            checkpoint()
        return original(text,query,offset,at_chunk)
    monkeypatch.setattr(occurrences,'_scan',scan)
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args,cancelled=cancel.is_set)
    assert error.value.code==('CANCELLED' if ending=='cancel' else 'PROJECT_FORBIDDEN')
    assert len(calls)==2 and children and all(child.poll() is not None for child in children)


@pytest.mark.parametrize('budget',['CPU_SECONDS','WALL_SECONDS'], ids=['cpu','wall'])
def test_expired_budget_reaps_owned_child(owned,monkeypatch,budget):
    ctx,options=owned;args=options(b'a'*100000)
    children=[];original=occurrences.RustInputSession.open_import
    def opened(session,*a,**kw):
        result=original(session,*a,**kw);children.append(session.process);monkeypatch.setattr(occurrences,budget,0);return result
    monkeypatch.setattr(occurrences.RustInputSession,'open_import',opened)
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='SOURCE_SEARCH_BUDGET_EXCEEDED'
    assert children and all(child.poll() is not None for child in children)


def test_revocation_masks_late_source_specific_scan_error(owned,monkeypatch):
    ctx,options=owned;args=options();children=track_children(monkeypatch)
    def denied(*a):
        with ctx.state.transaction(ctx.principal,write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
        raise CoreError('SOURCE_ENCODING_UNSUPPORTED','PRIVATE_SOURCE_DIAGNOSTIC')
    monkeypatch.setattr(occurrences,'_scan',denied)
    with pytest.raises(CoreError) as error:occurrences.search_source_occurrences(ctx,**args)
    assert error.value.code=='PROJECT_FORBIDDEN' and 'PRIVATE' not in str(error.value)
    assert children and all(child.poll() is not None for child in children)


def test_success_reaps_child_and_preserves_source_and_reference(owned,monkeypatch):
    ctx,options=owned;args=options();before=dict(args['reference']);raw=args['archive'].read_bytes();children=track_children(monkeypatch)
    assert occurrences.search_source_occurrences(ctx,**args)['input_ref']==before
    assert args['reference']==before and args['archive'].read_bytes()==raw
    assert children and all(child.returncode==0 for child in children)
