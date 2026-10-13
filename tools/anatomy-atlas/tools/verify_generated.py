#!/usr/bin/env python3
"""Verify deterministic generated outputs against the reviewed source manifest."""
import argparse
import hashlib
import json
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True,type=Path)
parser.add_argument('--manifest',type=Path,default=Path(__file__).resolve().parent.parent/'data/source-manifest.json')
args=parser.parse_args();manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
seed=args.manifest.parent/manifest['editorialSeed']
if hashlib.sha256(seed.read_bytes()).hexdigest()!=manifest['editorialSeedSha256']:raise SystemExit('Editorial seed checksum mismatch')
for name,expected in manifest['expectedArtifacts'].items():
 raw=(args.output/name).read_bytes()
 if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:raise SystemExit('Generated artifact mismatch: '+name)
print('Verified six deterministic artifacts at '+manifest['sourceCommit'])
