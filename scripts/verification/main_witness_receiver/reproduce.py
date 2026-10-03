"""Prospective operator CLI: measured inputs and calls to four reviewed helpers.
Author has not executed/imported/compiled this Source. Root effects require
explicit full-Source-read, compile and controls decisions from the operator.
Received accepted peer records are copied byte-for-byte, never synthesized.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, uuid

FILES = {
    'C': ('root_main_receiver.c', 75900, 'fe81974981d4ab20156814d1dfae6f90610cabb8f5a0fff0cebcbd49c3a8e16e'),
    'receiver_H': ('root_main_receiver.h', 5622, '92869b7a616198fbf8f6beb83f074e9e82df3a3cf000bbd454e0868248bef280'),
    'original_H': ('root_live_debug_birth.h', 6141, 'b14f94f5674ec55b2f8fc15900bb63e5b466ce21406042c6c204bdefae84328c'),
    'parent': ('fixtures/parent.cjs', 5294, '11015fc699e645f927f286b55db743cfaedf020eff60a39426b2b3ff6527118f'),
    'child': ('fixtures/child.cjs', 43, '5748b8d4f8bc52c6871ccf135e0fda61670a8e69c0567ff9419afcfac3476411'),
    'outer_helper': ('admit_two_cases.py', 8238, 'ab5ad443b3415936538b7598c05ab6c62018f167b2f60a453e683bbd958f78d3'),
    'launcher': ('launch_two_cases.py', 25644, '227c62a10907888df5141eb390a8a62fef0ff3e562ae385f61fc542f049927f0'),
    'verifier': ('verify_case.py', 47234, 'aea7cba7480578f6cae8a2268a24562445058e14e7bbdc5030de4ec5a07616e1'),
    'compiler_helper': ('compile_data_abis.py', 4931, '8d7129e4c990fd66fcdf16448a33394d6ca5f7643bed016e73a6f828e6358668'),
}
RLD = [1,8,65536,8,8368,24,16,32,152,120,20624,40]
RWR = [1,8,32768,8,1472,24,184,152,16,1024,4096,2,16]
CASES = ('expected_parent_slot0', 'expected_child_slot1')
FALSE_SCOPE = dict(EditorRole=False, OwnerIPC=False, daily_model_task_accepted=False,
                   new_tag_release_admitted=False, full_product_ready=False,
                   production_deployment=False, runtime_qualified=False)

def need(ok, why):
    if not ok:
        raise RuntimeError(why)

def absolute(value):
    p = Path(value)
    need(p.is_absolute() and len(p.drive) == 2 and p.drive[1] == ':' and
         not str(p).startswith('\\\\'), 'absolute local drive-rooted path')
    return p

def pin(p, cap=128*1024*1024):
    h, size = hashlib.sha256(), 0
    with p.open('rb') as f:
        while True:
            part = f.read(65536)
            if not part:
                break
            size += len(part)
            need(size <= cap, 'file cap')
            h.update(part)
    return dict(path=str(p), size_bytes=size, sha256=h.hexdigest())

def pairs(items):
    d = {}
    for key, value in items:
        need(key not in d, 'duplicate JSON key')
        d[key] = value
    return d

def json_bytes(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)

def read_ref(r, cap=1048576):
    p = absolute(r['path'])
    need(pin(p, cap) == r, 'exact retained ref')
    return json_bytes(p.read_bytes())

def review(path, sha):
    p = absolute(path)
    r = pin(p, 1048576)
    need(r['sha256'] == sha, 'operator-pinned genuine review SHA')
    raw = p.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == sha, 'review bytes changed')
    v = json_bytes(raw)
    need(type(v) is dict and v.get('accepted') is True, 'genuine accepted Source review required')
    return r, raw, v

def same_bytes(got, want):
    return type(got) is dict and set(got) == set(want) and all(
        type(got[k]) is dict and got[k].get('size_bytes') == want[k]['size_bytes'] and
        got[k].get('sha256') == want[k]['sha256'] for k in want)

def compiler_binding(v):
    return v.get('compiler_helper_ref', v.get('current_compiler_helper', v.get('compiler_helper')))

def save(p, value):
    raw = (json.dumps(value, ensure_ascii=True, indent=2)+'\n').encode('utf-8')
    need(len(raw) <= 1048576, 'own JSON cap')
    with p.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return pin(p, 1048576)

def copy_review(raw, p):
    with p.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return pin(p, 1048576)

def call_helper(argv, label, directory):
    out, err = directory/(label+'.stdout'), directory/(label+'.stderr')
    rc, timeout = None, False
    with out.open('xb') as a, err.open('xb') as b:
        try:
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=a, stderr=b,
                               cwd=str(directory), close_fds=True, shell=False,
                               timeout=90, check=False)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            timeout = True
    raw = save(directory/(label+'-raw-before-checks.json'), dict(
        argv=argv, returncode=rc, timed_out=timeout, stdout=pin(out), stderr=pin(err),
        scope='owned helper invocation only', **FALSE_SCOPE))
    need(not timeout and rc == 0 and out.stat().st_size <= 65536 and
         err.stat().st_size == 0, 'helper failure/unknown; raw retained at '+raw['path'])
    return json_bytes(out.read_bytes()), raw

def main():
    ap = argparse.ArgumentParser(description='Experimental compile plus two isolated transport controls')
    for name in ('source-root', 'evidence-root', 'node', 'python', 'native-review',
                 'native-review-sha', 'harness-review', 'harness-review-sha'):
        ap.add_argument('--'+name, required=True)
    ap.add_argument('--relocation-review')
    ap.add_argument('--relocation-review-sha')
    ap.add_argument('--Root-full-source-read', dest='source_read', action='store_true')
    ap.add_argument('--admit-compile', action='store_true')
    ap.add_argument('--admit-controls', action='store_true')
    cli = ap.parse_args()
    need(os.name == 'nt' and sys.maxsize > 2**32 and sys.version_info[:3] == (3,11,9) and
         sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize,
         'Windows x64/Python3.11.9/-I -S -B/no optimize')
    need(not (cli.admit_compile or cli.admit_controls) or cli.source_read,
         'explicit operator full Source read required before effects')
    need(not cli.admit_controls or cli.admit_compile, 'controls require actual compile in this fresh run')
    source, evidence = absolute(cli.source_root), absolute(cli.evidence_root)
    need(source.is_dir() and evidence.is_dir() and
         not source.resolve().is_relative_to(evidence.resolve()) and
         not evidence.resolve().is_relative_to(source.resolve()), 'disjoint source/evidence roots')
    package = source/'scripts/verification/main_witness_receiver'
    refs = {}
    for key, (name, size, sha) in FILES.items():
        r = pin(package/name)
        need((r['size_bytes'], r['sha256']) == (size, sha), 'fixed reviewed Source bytes: '+key)
        refs[key] = r
    node, python = pin(absolute(cli.node)), pin(absolute(cli.python))
    need((node['size_bytes'], node['sha256']) == (91694408, '3331e1ffe19874215472217c5e94f5a0c6d8e18c4ac7111d3937aa0ad5e9b4a5'),
         'exact reviewed Node image')
    need((python['size_bytes'], python['sha256']) == (103192, '5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec') and
         absolute(cli.python) == Path(sys.executable), 'exact current Python image')
    sources = {k:refs[k] for k in ('C','receiver_H','original_H')}
    harness = {k:refs[k] for k in ('outer_helper','launcher','verifier')}
    nr, nb, nv = review(cli.native_review, cli.native_review_sha)
    hr, hb, hv = review(cli.harness_review, cli.harness_review_sha)
    need(same_bytes(nv.get('current_sources'), sources), 'native review must cover these fixed public Source bytes')
    need(same_bytes(hv.get('current_harness_sources'), harness) and
         same_bytes({'compiler_helper':compiler_binding(hv)}, {'compiler_helper':refs['compiler_helper']}),
         'harness review must genuinely cover the fixed three helpers and compiler helper')
    direct = (nv.get('current_sources') == sources and hv.get('current_harness_sources') == harness and
              compiler_binding(hv) == refs['compiler_helper'])
    relocation = None
    if cli.relocation_review or cli.relocation_review_sha:
        need(cli.relocation_review and cli.relocation_review_sha, 'complete relocation review ref')
        rr, rb, rv = review(cli.relocation_review, cli.relocation_review_sha)
        fixed = {k:dict(size_bytes=v['size_bytes'], sha256=v['sha256']) for k,v in refs.items()}
        need(rv.get('schema') == 'rentgen-reviewed-main-receiver-source-relocation/1' and
             rv.get('scope') == 'source-path-relocation-only' and rv.get('approved_by') and
             rv.get('same_source_bytes') is True and rv.get('original_native_review') == nr and
             rv.get('original_harness_review') == hr and rv.get('fixed_source_pins') == fixed and
             rv.get('current_sources') == sources and rv.get('current_harness_sources') == harness and
             rv.get('compiler_helper_ref') == refs['compiler_helper'] and
             all(rv.get(k) is False for k in FALSE_SCOPE) and rv.get('D8') == 'OPEN',
             'actual reviewer-approved exact same-byte relocation required')
        relocation = rr, rb
    need(direct or relocation is not None, 'raw Source paths differ; obtain genuine reviewer relocation approval')
    work = evidence/('public-main-receiver-reproduction-'+uuid.uuid4().hex)
    work.mkdir()
    native = copy_review(nb, work/'genuine-native-review.json')
    harness_peer = copy_review(hb, work/'genuine-harness-review.json')
    peer_refs = [native, harness_peer]
    if relocation is not None:
        relocated = copy_review(relocation[1], work/'genuine-relocation-review.json')
        native = relocated
        peer_refs.append(relocated)
    inputs = dict(C=refs['C'], header=refs['receiver_H'], base_header=refs['original_H'],
                  node=node, parent=refs['parent'], child=refs['child'])
    admission = save(work/'compile-admission.json', dict(
        schema='rentgen-Root-public-Main-receiver-compile-dataABI-admission/1',
        evidence_root=str(work), compiler_helper=refs['compiler_helper'],
        Root_full_Source_read=cli.source_read, Root_compile_admitted=cli.admit_compile,
        Root_data_ABI_only_admitted=cli.admit_compile, fixture_runtime_admitted=False,
        independent_Source_peer=native, sources=sources, expected_rld_abi=RLD, expected_rwr_abi=RWR))
    compile_argv = [python['path'],'-I','-S','-B','-X','utf8','-u',refs['compiler_helper']['path'],
                    '--evidence-root',str(work),'--admission',admission['path'],'--admission-sha',admission['sha256']]
    manifest = save(work/'measured-inputs-and-operator-decisions.json', dict(
        source_root=str(source), evidence_root=str(evidence), owned_run_directory=str(work),
        actual_sources=refs, node=node, python=python, actual_wrapper=pin(Path(__file__)),
        original_native_review=nr, original_harness_review=hr,
        relocation_review=relocation[0] if relocation else None,
        compile_admission=admission, compile_argv=compile_argv,
        Root_full_Source_read=cli.source_read, Root_compile_admitted=cli.admit_compile,
        Root_controls_admitted=cli.admit_controls, **FALSE_SCOPE))
    result = dict(manifest=manifest, owned_run_directory=str(work), **FALSE_SCOPE)
    if not cli.admit_compile:
        print(json.dumps(dict(result, prepared_only=True)), flush=True)
        return
    actual, raw = call_helper(compile_argv, 'compile-helper', work)
    cr_ref = actual['receipt']
    need(absolute(cr_ref['path']).resolve().is_relative_to(work.resolve()), 'actual compile receipt in chosen root')
    cr = read_ref(cr_ref)
    need(cr['returncode'] == 0 and cr['timed_out'] is False and cr.get('ABI_matches') is True and
         cr['reviewed_sources'] == sources and cr['Root_admission'] == admission and
         cr['actual_rld_abi'] == RLD and cr['actual_rwr_abi'] == RWR and
         cr['actual_rwr_abi_raw32'] == RWR+[0]*19 and cr['fixture_runtime_executed'] is False and
         cr['init_register_run_submit_called'] is False, 'actual compile/data ABI binding only')
    need(absolute(cr['DLL']['path']).resolve().is_relative_to(work.resolve()), 'actual DLL confined to same root')
    need(pin(absolute(cr['DLL']['path'])) == cr['DLL'], 'actual newly measured DLL')
    inputs['dll'] = cr['DLL']
    request = save(work/'two-controls-request.json', dict(
        schema='rentgen-Root-public-Main-receiver-runtime-request/1', source_root=str(source),
        evidence_root=str(work), outer_helper=refs['outer_helper'], launcher=refs['launcher'],
        verifier=refs['verifier'], inputs=inputs, compile_receipt=cr_ref,
        independent_Source_peers=peer_refs, Root_full_Source_read=cli.source_read,
        Root_fixture_runtime_admitted=cli.admit_controls, **FALSE_SCOPE))
    result.update(compile_receipt=cr_ref, compile_raw=raw, runtime_request=request)
    if cli.admit_controls:
        argv = [python['path'],'-I','-S','-B','-X','utf8','-u',refs['outer_helper']['path'],
                '--evidence-root',str(work),'--request',request['path'],'--request-sha',request['sha256']]
        outer, outer_raw = call_helper(argv, 'two-controls-helper', work)
        need(outer['returncode'] == 0 and outer['timed_out'] is False and outer['stderr_text'] == '',
             'actual outer launcher/stdio failure or unknown')
        lines = [json_bytes(line.encode('utf-8')) for line in outer['stdout_lines']]
        need(len(lines) == 3 and all(v.get('accepted_synthetic_receiver_only') is True for v in lines),
             'two cases and one actual retained summary required')
        summary_ref = lines[-1]['retained']
        summary = read_ref(summary_ref)
        ad_ref = summary['Root_execution_admission_ref']
        ad = read_ref(ad_ref)
        need(ad['schema'] == 'rentgen-Root-Main-receiver-two-hosts-execution-admission/2' and
             ad['evidence_root'] == str(work) and set(ad['case_seeds']) == set(CASES) and
             summary['accepted_synthetic_receiver_only'] is True and len(summary['cases']) == 2,
             'actual same-root two-case admission/summary')
        for name in CASES:
            seed = read_ref(ad['case_seeds'][name])
            config = pin(absolute(seed['working_directory'])/'config.json', 16384)
            cfg = read_ref(config, 16384)
            need(cfg['case'] == name and cfg['generation'] == seed['generation'] and
                 cfg['session_cookie'] == seed['session_cookie'] and cfg['receiver'] == seed['receiver'],
                 'exact original two seed/config joins')
        result.update(outer_raw=outer_raw, actual_two_controls_summary=summary_ref,
                      actual_two_seed_config_pairs=2)
    final = save(work/'operator-reproduction-result.json', result)
    print(json.dumps(dict(result_ref=final, **FALSE_SCOPE)), flush=True)

if __name__ == '__main__':
    main()