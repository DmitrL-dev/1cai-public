"""Fetch exact official test observers into a new disposable build directory."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import urllib.request
from instrument import instrument

PINS = {
    '6.8': ('ba6950a96824cdf93a584fa04f0a733896d2a6bc5f0ad9ffe505d9b41e970149',2457948),
    '6.12': ('c47da93be45b6055f4dc741d7f20efaf50ca10160a5b100c109b294fd9c0bdfe',2628804),
}

def main():
    if len(sys.argv)!=2: raise SystemExit('one new output directory required')
    root=Path(sys.argv[1]).resolve();root.mkdir(mode=0o700,exist_ok=False)
    inventory=[]
    for version,(expected,size) in PINS.items():
        url=f'https://strace.io/files/{version}/strace-{version}.tar.xz'
        with urllib.request.urlopen(url,timeout=30) as response: data=response.read(size+1)
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=expected:
            raise RuntimeError('official observer archive pin mismatch')
        archive=root/f'strace-{version}.tar.xz';archive.write_bytes(data)
        with tarfile.open(archive) as package:
            for member in package:
                if not (root/member.name).resolve().is_relative_to(root):
                    raise RuntimeError('archive escaped build root')
            package.extractall(root,filter='data')
        inventory.append({'version':version,'url':url,'bytes':size,'sha256':expected})
    (root/'official-source-downloads.json').write_text(json.dumps(inventory,indent=2)+'\n')
    instrument(root)
    (root/'synthetic-stat-target').write_bytes(b'x')

if __name__=='__main__': main()
