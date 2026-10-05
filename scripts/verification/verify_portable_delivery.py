"""Install the exact candidate wheel in a fresh environment and verify Linux CLI.

Creates only new synthetic inputs under the explicit output directory. No model,
network downloads, project import, live apply or existing user profile is used.
"""
if not __debug__:
    raise RuntimeError('Delivery verification requires assertions; do not use Python -O')

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import venv
import zipfile


def verify(wheel, binary, output, expected_version):
    wheel, binary, output = wheel.resolve(strict=True), binary.resolve(strict=True), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = output / 'environment'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / 'bin/python'
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)], check=True, capture_output=True, text=True, timeout=60)
    core = output / 'rentgen-input-core'
    shutil.copyfile(binary, core); core.chmod(0o700)
    core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
    workspace = output / 'work'; workspace.mkdir()
    probe = subprocess.run([str(python), '-I', '-c', 'import importlib.metadata,json,rentgen_core,sys;from pathlib import Path;print(json.dumps({"version":importlib.metadata.version("rentgen-core"),"installed":Path(rentgen_core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())}))'], cwd=workspace, capture_output=True, text=True, check=True, timeout=15)
    assert json.loads(probe.stdout) == {'version': expected_version, 'installed': True}
    checks = []
    def cli(*args, expected=0):
        result = subprocess.run([str(python), '-I', '-m', 'rentgen_core', *map(str, args)], cwd=workspace, capture_output=True, text=True, timeout=30)
        assert result.returncode == expected and not result.stderr, (result.stdout, result.stderr)
        value = json.loads(result.stdout); checks.append({'command': args[0], 'exit': result.returncode})
        return value
    profile = workspace / 'private/identity.json'
    registry = workspace / 'registry.sqlite3'
    source = workspace / 'source'; source.mkdir(); (source / 'untouched.bsl').write_bytes(b'Unchanged();\n')
    cli('identity-init', '--identity-profile', profile)
    common = ['--registry', registry, '--identity-profile', profile]
    cli('registry-init', *common)
    project = cli('project-register', *common, '--source-root', source, '--state-root', workspace / 'state', '--name', 'Installed portable qualification')['result']['project_id']
    archive = workspace / 'export.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        target.writestr('Catalogs/Products.xml', '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"><Catalog uuid="11111111-1111-4111-8111-111111111111"><Properties><Name>Products</Name></Properties><ChildObjects/></Catalog></MetaDataObject>')
        target.writestr('CommonModules/Shared/Ext/Module.bsl', 'Procedure Demo()\nEndProcedure\n')
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    args = ['export-analyze', *common, '--project', project, '--archive', archive, '--archive-sha256', archive_hash, '--input-core', core, '--input-core-sha256', core_hash]
    report = cli(*args)['result']
    assert report['counts']['metadata_objects'] == 1 and report['counts']['modules'] == 1
    assert cli(*args)['result'] == report
    assert cli('project-head', *common, '--project', project)['result']['snapshot'] is None
    assert (source / 'untouched.bsl').read_bytes() == b'Unchanged();\n'
    refused = cli('capture', *common, '--project', project, expected=2)
    assert refused['error']['code'] == 'CAPABILITY_UNAVAILABLE'
    receipt = {'schema': 1, 'scope': 'experimental Linux installed CLI import; not Windows/macOS or full Linux qualification', 'version': expected_version, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(), 'binary_sha256': core_hash, 'checks': checks, 'counts': report['counts'], 'source_unchanged': True, 'project_head_unchanged': True}
    (output / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Experimental Linux delivery qualification only')
    verify(args.wheel, args.binary, args.output, args.expected_version)


if __name__ == '__main__':
    main()
