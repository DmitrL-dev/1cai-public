"""Hash-bound owned development controls. They are never an independent holdout."""
from pathlib import Path
import hashlib
import re
from .contracts import CHECKS, HYPOTHESES, bounded_json, enum, exact, integer, require, validate_envelope


def read_bound(path, maximum, failure):
    """Bound allocation before JSON/hash admission, including a changed file."""
    with path.open('rb') as source:
        raw = source.read(maximum + 1)
    require(len(raw) <= maximum, failure)
    return raw


def load(directory):
    directory = Path(directory).resolve(strict=True)
    manifest_path = directory / 'manifest.json'
    require(not manifest_path.is_symlink(), 'corpus_link')
    manifest = bounded_json(read_bound(manifest_path, 65536, 'input_limit'))
    exact(manifest, 'schema license origin heldout native_verified files')
    require(type(manifest['schema']) is int and manifest['schema'] == 1, 'invalid_version')
    require(manifest['license'] == 'MIT' and manifest['origin'] == 'owned_synthetic_controls'
            and manifest['heldout'] is False and manifest['native_verified'] is False, 'unqualified_provenance')
    require(type(manifest['files']) is list and 1 <= len(manifest['files']) <= 8, 'corpus_limit')
    cases = []; seen_files = set(); total = 0
    for item in manifest['files']:
        exact(item, 'path sha256 size_bytes')
        require(type(item['path']) is str and re.fullmatch('[a-z0-9_-]+\.json', item['path']) is not None
                and item['path'] not in seen_files, 'corpus_path')
        seen_files.add(item['path']); integer(item['size_bytes'], 1, 512 * 1024)
        require(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']) is not None, 'corpus_hash')
        path = directory / item['path']; require(not path.is_symlink() and path.is_file(), 'corpus_file')
        raw = read_bound(path, min(item['size_bytes'], 512 * 1024, 1024 * 1024 - total), 'corpus_hash_mismatch')
        total += len(raw)
        require(total <= 1024 * 1024 and len(raw) == item['size_bytes']
                and hashlib.sha256(raw).hexdigest() == item['sha256'], 'corpus_hash_mismatch')
        bundle = bounded_json(raw, 512 * 1024)
        require(type(bundle) is list and 1 <= len(bundle) <= 64, 'case_limit')
        for case in bundle:
            validate_case(case); cases.append(case)
    ids = [c['id'] for c in cases]
    require(len(set(ids)) == len(ids) and len(cases) <= 128, 'duplicate_case')
    return manifest, cases


def validate_case(case):
    exact(case, 'id family pair phase initial outcomes expected provenance')
    integer(case['id'], 1)
    for key in ['family', 'pair']:
        require(type(case[key]) is str and re.fullmatch('[a-z0-9_]{1,48}', case[key]) is not None, 'case_label')
    enum(case['phase'], {'before', 'after', 'control'})
    initial = validate_envelope(case['initial'])
    require(initial['scope']['case_id'] == case['id'], 'case_binding')
    require(type(case['outcomes']) is dict and not set(case['outcomes']) - set(CHECKS), 'invalid_outcomes')
    for check, outcome in case['outcomes'].items():
        exact(outcome, 'status facts')
        enum(outcome['status'], {'observed', 'timeout', 'unavailable'})
        require(type(outcome['facts']) is list and len(outcome['facts']) <= 3, 'invalid_outcome')
    exact(case['expected'], 'supported refuted sufficient_possible')
    require(type(case['expected']['sufficient_possible']) is bool, 'invalid_expectation')
    for field in ['supported', 'refuted']:
        require(type(case['expected'][field]) is list and len(case['expected'][field]) <= 5, 'invalid_expectation')
        for hypothesis in case['expected'][field]:
            enum(hypothesis, HYPOTHESES)
        require(len(case['expected'][field]) == len(set(case['expected'][field])), 'duplicate_expectation')
    require(not set(case['expected']['supported']) & set(case['expected']['refuted']), 'contradictory_expectation')
    exact(case['provenance'], 'license origin heldout native_verified')
    require(case['provenance'] == {'license': 'MIT', 'origin': 'owned_synthetic_control',
            'heldout': False, 'native_verified': False}, 'unqualified_provenance')
