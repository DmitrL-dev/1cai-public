"""Hold a real child process inside an observer SQLite write, then kill it."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]

# The child replaces the observer fault-injection hook. It signals only after
# the named boundary, i.e. inside the open BEGIN IMMEDIATE write transaction.
BLOCK_AT = """
import sys, time
from pathlib import Path
import rentgen_core.observer as implementation

def _block(name, _ready=Path(sys.argv[-1]), _at=sys.argv[-2]):
    if name == _at:
        _ready.write_text("blocked")
        time.sleep(300)

implementation._boundary = _block
"""


@contextmanager
def killed_inside_write(code, *args, boundary, ready, timeout=180):
    """Yield while the child is blocked at ``boundary``; kill it on exit."""
    child = subprocess.Popen(
        [sys.executable, "-c", BLOCK_AT + code, *map(str, args), boundary, str(ready)],
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + timeout
        while not (ready.exists() and ready.read_text() == "blocked"):
            if child.poll() is not None:
                _, errors = child.communicate(timeout=30)
                raise AssertionError(
                    "Child exited before the write boundary: "
                    + errors.decode(errors="replace")[-2000:]
                )
            if time.monotonic() >= deadline:
                raise AssertionError("Child did not reach the write boundary")
            time.sleep(0.05)
        yield child
        assert child.poll() is None, "Child must still hold the open write"
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=30)
    assert child.returncode != 0
