"""Portable fail-closed startup checks; no Core/native imports or fixtures."""
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]


class VerificationOptimizationTests(unittest.TestCase):
    def check_guard(self, verifier, optimization):
        script = f"""
import sys
sys.path.insert(0, 'scripts/verification')
verifier = {verifier!r}
class RejectVerificationImports:
    def find_spec(self, fullname, path=None, target=None):
        blocked = {{'argparse', 'rentgen_core', 'verify_edt_metadata_fixture'}} - {{verifier}}
        if fullname in blocked:
            raise RuntimeError('unexpected import before optimization guard: ' + fullname)
        return None
sys.meta_path.insert(0, RejectVerificationImports())
try:
    __import__(verifier)
except RuntimeError as error:
    if str(error) != 'Verification requires assertions; do not use Python -O':
        raise
else:
    raise RuntimeError('optimized verifier was accepted')
"""
        result = subprocess.run(
            [sys.executable, "-I", "-S", optimization, "-B", "-c", script],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(
            result.returncode, 0, result.stderr.decode("utf-8", errors="replace")
        )
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")

    def test_migration_rejects_O_before_imports(self):
        self.check_guard("verify_metadata_migration", "-O")

    def test_migration_rejects_OO_before_imports(self):
        self.check_guard("verify_metadata_migration", "-OO")

    def test_direct_edt_rejects_O_before_imports(self):
        self.check_guard("verify_edt_metadata_fixture", "-O")

    def test_direct_edt_rejects_OO_before_imports(self):
        self.check_guard("verify_edt_metadata_fixture", "-OO")


if __name__ == "__main__":
    unittest.main()
