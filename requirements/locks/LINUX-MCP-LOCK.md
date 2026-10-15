# Candidate Linux MCP dependency inputs

`mcp-py311-linux-x86_64.txt` selects **29 original binary wheels** for the
existing `mcp==1.30.0` optional dependency. It is a prerequisite for an experimental
offline kit, not a release receipt or proof of a working Linux installation.

The explicit target is **CPython 3.11.15, GNU/Linux x86_64, glibc >= 2.34**.
Python 3.12 remains an ordinary CI target; this lock does not admit it, macOS,
Windows, musl, ARM or arbitrary native `linux_x86_64` wheels. Pure `py3-none-any`
wheels and compatible older CPython `abi3` wheels are allowed. The selected native
wheels are:

| Package | Selected ABI/platform |
| --- | --- |
| cffi 2.1.1 | cp311 / manylinux 2.17 x86_64 |
| cryptography 50.0.1 | cp311 abi3 / manylinux 2.34 x86_64 |
| pydantic-core 2.46.5 | cp311 / manylinux 2.17 x86_64 |
| rpds-py 2026.6.3 | cp311 / manylinux 2.17 x86_64 |

Every version is retained from the existing Windows MCP lock; no package was
upgraded for this candidate. Linux marker evaluation excludes `pywin32`.
`pyjwt[crypto]` activates `cryptography`, which requires `cffi` and `pycparser` on
this target. Optional CLI, rich, websocket, HTTP/2 and server-standard extras are
not selected. A transitive extra is evaluated together with that package's base
dependencies; a marker is never evaluated using the machine running the checker.
Kernel release/version markers are refused because this lock does not qualify
one particular kernel version.

The matching `.provenance.json` records each original filename, version, PyPI
release JSON URL and digest, wheel URL/size/SHA256, wheel METADATA digest and raw
requirements, and the paths/sizes/digests of license or notice files retained in
that wheel. These are dependency input records, not authority to accept a kit.
The release JSON and wheel were fetched from `pypi.org` and
`files.pythonhosted.org`; the original JSON size/hash was recorded, then the
wheel's original PyPI size and SHA256 were checked **before ZIP metadata reads**.
Wheel contents were not imported, executed or extracted during this audit.
The selected wheel bytes total **9,418,024 bytes**. Preserve original wheels and
their license/notice files when packaging; filenames alone are insufficient.

Resolution used `uv 0.11.28` on macOS with an explicit target, constrained by the
existing version pins (without their Windows wheel hashes):

```sh
uv pip compile roots.in --constraints prior-pins.txt \
  --python-version 3.11.15 --python-platform x86_64-manylinux_2_34 \
  --only-binary=:all: --no-python-downloads --default-index https://pypi.org/simple \
  --no-sources --no-cache --output-file resolved.txt
```

`roots.in` contains only `mcp==1.30.0`; `prior-pins.txt` contains the exact
name/version pairs from `mcp-py311-windows.txt`. The provenance identifies the
resolution's source revision and both source input digests. Those are historical
resolution inputs; a future kit must separately bind its own exact source commit
and these lock/provenance/checker bytes.

For an already downloaded wheelhouse, the build-time checker uses `packaging`
from the existing development/build environment. It performs no network access:

```sh
python requirements/locks/check_linux_mcp_lock.py --wheelhouse /path/to/wheelhouse
```

The directory must contain exactly the 29 selected original wheels. The checker
compares the requirements lock with provenance, evaluates the complete selected
dependency/extra graph against the explicit target, checks original wheel
sizes/hashes before opening ZIPs, and walks the actual central-directory records
before constructing `ZipFile`; EOCD counts alone are insufficient. It bounds
record counts, directory/name/extra/comment/expanded sizes, requires the exact
directory end, and refuses ZIP64, multiple disks and overlapping local records.
It then verifies dependency identity, wheel tags and license bytes. The API is
`verify_wheelhouse(path, *, provenance_path=..., lock_path=...)`; packagers may
stage these inputs from exact Git blobs. This checker does not establish hostile
filesystem ownership or remove an installer's duty to validate its final archive.

Before admitting a Linux kit, run on an actual supported Linux x86_64 machine
with the **same CPython 3.11.15 target** in a fresh venv:

```sh
python -m pip install --no-index --only-binary=:all: --require-hashes \
  --find-links /path/to/wheelhouse -r mcp-py311-linux-x86_64.txt
python -m pip check
```

Also verify installed-module origins and bytes, then use the real installed SDK
stdio client/server for capture, retained source/graph/history reads, replay and
cancellation. The full runtime must be installed from accepted local inputs;
an online dependency install or source-checkout MCP smoke does not close this
gate. **Native Linux offline install, `pip check` and installed SDK acceptance
have not run for this candidate.** No GitHub CI or release success is claimed.
