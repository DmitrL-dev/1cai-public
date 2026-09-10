"""Trusted local installation layout; proposal JSON selects only a fixed profile.

Construction and selection perform no filesystem IO. The concrete adapter and
its Windows process owner survive calls, including failed cleanup. This module
never downloads or updates runtimes and never inherits a tool-supplied command.
"""
import os
from pathlib import Path
from threading import Lock

from rentgen_core.diagnostics import BSL_PROFILE_ID
from rentgen_core.errors import CoreError


class InstalledDiagnostics:
    def __init__(self, *, local_app_data: Path | None = None):
        configured = (
            os.environ.get("LOCALAPPDATA") if local_app_data is None else local_app_data
        )
        self._base = Path(configured) if configured else None
        if self._base is not None and not self._base.is_absolute():
            self._base = None
        self._adapter = None
        self._initialization_lock = Lock()

    def for_profile(self, profile_id: str):
        if type(profile_id) is not str or profile_id != BSL_PROFILE_ID:
            raise CoreError(
                "DIAGNOSTIC_PROFILE_UNAVAILABLE",
                "Select the supported installed diagnostics profile",
            )
        if self._base is None:
            raise CoreError(
                "DIAGNOSTIC_RUNTIME_UNAVAILABLE",
                "An absolute trusted LOCALAPPDATA installation root is required",
            )
        return self

    def analyze(self, candidate_bytes: bytes, *, suffix: str, authorize):
        authorize()
        # Keep one adapter even when its owner becomes poisoned. A fresh tool call
        # cannot discard an uncertain process tree or its retained input handles.
        with self._initialization_lock:
            if self._adapter is None:
                self.for_profile(BSL_PROFILE_ID)
                try:
                    from .bsl_language_server import (
                        BslLanguageServerAdapter,
                        BslRuntimeProfile,
                    )
                except ImportError as exc:
                    raise CoreError(
                        "DIAGNOSTIC_RUNTIME_UNAVAILABLE",
                        "Install the supported diagnostics adapter",
                    ) from exc
                runtime = self._base / "Rentgen" / "runtimes" / BSL_PROFILE_ID
                self._adapter = BslLanguageServerAdapter(
                    BslRuntimeProfile(
                        java_home=runtime / "jdk",
                        jar_path=runtime / "bsl-language-server.jar",
                        work_parent=self._base / "Rentgen" / "diagnostic-runs",
                    )
                )
            adapter = self._adapter
        return adapter.analyze(candidate_bytes, suffix=suffix, authorize=authorize)
