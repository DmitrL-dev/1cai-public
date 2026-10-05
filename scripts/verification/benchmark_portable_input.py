"""Synthetic benchmark for experimental Linux import; never reads project data.

Timing excludes common Python adapter import (recorded separately). Rust timing
includes verified executable launch, import, and paged inventory IPC.
The Python reference is a test-only zipfile/hash oracle without equivalent
confinement. Timings are observations, not a speedup or safety-equivalence claim.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sample(mode, binary, archive):
    startup = time.perf_counter()
    from rentgen_core.rust_input import RustInputSession
    adapter_import_ms = (time.perf_counter() - startup) * 1000
    expected = json.loads(archive.with_suffix('.json').read_text())
    started = time.perf_counter()
    if mode == 'rust':
        with RustInputSession(binary, hashlib.sha256(binary.read_bytes()).hexdigest(), authorize=lambda: None) as session:
            manifest = session.open_import(archive, expected['archive_sha256'])
            entries = session.entries(manifest)
            actual = {item['path']: {'size_bytes': item['size_bytes'], 'raw_sha256': item['raw_sha256']} for item in entries}
            metadata = next(item for item in entries if item['path'] == 'Catalogs/Products.xml')
            assert hashlib.sha256(session.read_entry(metadata)).hexdigest() == expected['files']['Catalogs/Products.xml']['raw_sha256']
    else:
        actual = {}
        raw = archive.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected['archive_sha256']
        with zipfile.ZipFile(io.BytesIO(raw)) as oracle:
            for name in oracle.namelist():
                data = oracle.read(name)
                actual[name] = {'size_bytes': len(data), 'raw_sha256': hashlib.sha256(data).hexdigest()}
    assert actual == expected['files']
    return {
        'elapsed_ms': (time.perf_counter() - started) * 1000,
        'adapter_import_ms_excluded': adapter_import_ms,
        'python_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'parity': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--sample-mode', choices=('rust', 'python_reference'))
    parser.add_argument('--sample-archive', type=Path)
    args = parser.parse_args()
    if args.sample_mode:
        print(json.dumps(sample(args.sample_mode, args.binary, args.sample_archive)))
        return
    if not 1 <= args.samples <= 7 or args.output_directory is None:
        parser.error('Use a new output directory and 1..7 samples')
    root = args.output_directory.resolve(); root.mkdir(parents=True, exist_ok=False)
    binary = root / 'rentgen-input-core'
    shutil.copyfile(args.binary, binary); binary.chmod(0o700)
    xml = b'<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"><Catalog uuid="11111111-1111-4111-8111-111111111111"><Properties><Name>Products</Name></Properties><ChildObjects/></Catalog></MetaDataObject>'
    cases = {
        'small': {'Catalogs/Products.xml': xml, **{f'modules/{i:04}.bsl': b'Procedure Demo()\nEndProcedure\n' for i in range(10)}},
        'many_files': {'Catalogs/Products.xml': xml, **{f'assets/{i:04}.bin': b''.join(hashlib.sha256(f'{i}:{j}'.encode()).digest() for j in range(64)) for i in range(512)}},
        'decoded_24mib': {'Catalogs/Products.xml': xml, **{f'assets/{i:04}.bin': bytes([65 + i]) * (3 * 1024**2) for i in range(8)}},
    }
    reports = []
    for name, files in cases.items():
        archive = root / (name + '.zip')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path, data in files.items():
                output.writestr(path, data)
        expected = {'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': {path: {'size_bytes': len(data), 'raw_sha256': hashlib.sha256(data).hexdigest()} for path, data in files.items()}}
        archive.with_suffix('.json').write_text(json.dumps(expected))
        case = {'case': name, 'files': len(files), 'compressed_bytes': archive.stat().st_size, 'decoded_bytes': sum(map(len, files.values())), 'modes': {}}
        for mode in ('rust', 'python_reference'):
            values = []
            for _ in range(args.samples):
                result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--binary', str(binary), '--sample-mode', mode, '--sample-archive', str(archive)], cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT)}, capture_output=True, text=True, timeout=70, check=True)
                values.append(json.loads(result.stdout))
            case['modes'][mode] = {'samples': values, 'median_elapsed_ms': statistics.median(item['elapsed_ms'] for item in values), 'max_child_rss_kib': max(item['child_peak_rss_kib'] for item in values), 'max_python_rss_kib': max(item['python_peak_rss_kib'] for item in values)}
        reports.append(case)
    receipt = {'schema': 1, 'platform': sys.platform, 'python': sys.version, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'scope': 'synthetic operation observations excluding common Python adapter import; Rust includes executable verification/process/IPC; Python reference lacks equivalent confinement', 'cases': reports}
    (root / 'benchmark.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
