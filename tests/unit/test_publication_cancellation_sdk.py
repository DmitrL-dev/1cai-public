"""Actual Windows source SDK rehearsal; installed acceptance runs separately."""
import importlib.util
import sys

import anyio
import pytest

from publication_kill_support import ROOT
from test_publication_process_kill import scanner


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows SDK publication cancellation")
def test_native_windows_sdk_cancel_drain_retry_and_late_receipt(scanner, tmp_path):
    spec = importlib.util.spec_from_file_location("publication_cancellation_probe",
        ROOT / "scripts/verification/publication_cancellation_probe.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    async def scenario():
        with anyio.fail_after(120):
            result = await probe.verify(sys.executable, scanner[0], tmp_path / "sdk",
                                        isolated=False, checkout=ROOT)
        assert result["transport"] == "official_sdk_stdio" and result["isolated"] is False
        assert len(result["cancellations"]) == 2 and all(result["outcomes"].values())
    anyio.run(scenario)
