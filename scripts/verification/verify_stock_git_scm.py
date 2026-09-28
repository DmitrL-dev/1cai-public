"""Qualify one owned installed stock Git/BSL service, never a deployed service."""
if not __debug__:
    raise RuntimeError('Stock acceptance requires assertions; do not use Python -O')

import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile


def load_script(name):
    spec=importlib.util.spec_from_file_location('rentgen_stock_runner_'+name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def runner_scripts(worker):
    return {name:worker.sha(Path(__file__).with_name(name)) for name in
        ('verify_stock_git_scm.py','scm_stock_git_lifecycle.py','scm_stock_git_measurement.py')}


def runtime_stage(workdir,mode,*,java_home=None,jar=None):
    worker=load_script('scm_acceptance_worker');prep=worker.configure(workdir)
    fixture=load_script('scm_stock_git_fixture')
    binding=worker.B/'stock-coordinator.json'
    if mode=='prepare':
        worker.require(not binding.exists(),'Stock coordinator evidence must be new')
        worker.require(java_home is not None and jar is not None,'Local pinned runtime inputs required')
        fixture.prepare_stock(worker,prep,java_home=java_home,jar=jar)
        worker.save(binding,{'schema':1,'workdir':str(workdir),'source_commit':prep['source_commit'],
            'kit_sha256':prep['kit_sha256'],'scripts':runner_scripts(worker),'actual_localservice_exercised':False})
        return 0
    stored=fixture.read_object(binding)
    expected={'schema':1,'workdir':str(workdir),'source_commit':prep['source_commit'],
        'kit_sha256':prep['kit_sha256'],'scripts':runner_scripts(worker),'actual_localservice_exercised':False}
    worker.require(stored==expected,'Stock coordinator source/kit/scripts binding differs')
    context,extra,files=fixture.inspect_stock(worker,prep)
    authority,service=context[6],context[5]
    authority={**authority,'debug_privilege':any(row['name']=='SeDebugPrivilege' for row in context[3].privileges())}
    context=(*context[:6],authority)
    ready=service.get('exists') is False and all(authority.get(key) is True for key in
        ('elevated','create_access','backup_privilege','restore_privilege','debug_privilege'))
    metadata={'schema':1,'source_commit':prep['source_commit'],'kit_sha256':prep['kit_sha256'],
        'wheel_sha256':prep['wheel_sha256'],'scanner_sha256':prep['scanner_sha256'],
        'installed_core_files':prep['installed_core_files'],'auxiliary_preparation':extra,
        'runner_scripts':stored['scripts'],'service_name':worker.NAME}
    inspection={**metadata,'authority':authority,'service_exists':service['exists'],'ready_for_privileged_run':ready,
        'input_hashes_verified':True,'mutations_performed':False,'recorded_utc':datetime.now(timezone.utc).isoformat()}
    worker.save(worker.B/'stock-inspection.json',inspection)
    if mode=='inspect':
        print(json.dumps(inspection));return 0
    lifecycle=load_script('scm_stock_git_lifecycle')
    worker.require(mode=='run','Unknown stock native stage')
    lifecycle.require_ready(worker,context)
    output=worker.B/'lifecycle';output.mkdir(exist_ok=False)
    worker.BUDGET=worker.Budget()
    cls=lifecycle.acceptance_type(worker,fixture,load_script('scm_git_probe_service'),
        load_script('scm_git_diagnostic_control'),load_script('scm_stock_git_control'),
        load_script('scm_stock_git_acl'),load_script('scm_stock_git_measurement'))
    test=cls(context,output,extra,files)
    result=lifecycle.run_lifecycle(test,worker,metadata)
    print(json.dumps({'output':str(output),'native_stock_git_accepted':result['native_stock_git_accepted'],
        'failure':result['failure'],'cleanup_errors':result['cleanup_errors']}))
    return 0 if result['native_stock_git_accepted'] else 2


def main(argv=None):
    values=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description=__doc__)
    if values[:1]==['--workdir']:
        parser.add_argument('--workdir',type=Path,required=True)
        parser.add_argument('mode',choices=('prepare','inspect','run'))
        parser.add_argument('--java-home',type=Path);parser.add_argument('--jar',type=Path)
        args=parser.parse_args(values)
        return runtime_stage(args.workdir,args.mode,java_home=args.java_home,jar=args.jar)
    for name in ('kit','build-receipt','output','java-home','jar'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-commit',required=True);parser.add_argument('--run',action='store_true')
    args=parser.parse_args(values);delivery=load_script('verify_service_scm_delivery')
    parent=Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))
    output=delivery.validate_output(args.output,parent)
    java,jar=args.java_home.resolve(strict=True),args.jar.resolve(strict=True)
    python,_=delivery.prepare(args.kit.resolve(strict=True),args.build_receipt.resolve(strict=True),args.expected_commit,output)
    coordinator=Path(__file__).resolve();evidence=output/'evidence'
    delivery.run(python,[coordinator,'--workdir',output,'prepare','--java-home',java,'--jar',jar],evidence,'stock-prepare')
    delivery.run(python,[coordinator,'--workdir',output,'inspect'],evidence,'stock-inspect')
    if args.run: delivery.run(python,[coordinator,'--workdir',output,'run'],evidence,'stock-lifecycle',timeout=1260)
    print(json.dumps({'output':str(output),'prepared':True,'scm_requested':args.run,
        'acceptance_source':str(evidence/'lifecycle/acceptance.json'),'production_deployment':False}))
    return 0


if __name__=='__main__': raise SystemExit(main())
