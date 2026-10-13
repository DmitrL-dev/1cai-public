"""Bounded test-only evidence for service-composition waits."""
import json
from pathlib import Path, PureWindowsPath
import sys
import traceback

from rentgen_core.service_entry import (
    RunResult, _FAILURE_STAGES, _FAILURE_KINDS, _FAILURE_REASONS,
)


def wait_diagnostic(thread, started, entered, finished, results):
    frame = sys._current_frames().get(thread.ident)
    try:
        stack = [] if frame is None else [
            {"file": PureWindowsPath(Path(item.filename).name).name[:80],
             "function": item.name[:80], "line": item.lineno}
            for item in traceback.StackSummary.extract(
                traceback.walk_stack(frame), limit=8, lookup_lines=False)
        ]
    finally:
        del frame
    safe = []
    for result in results[:3]:
        if type(result) is not RunResult:
            safe.append({"invalid_result": True})
            continue
        row = {"cycles": result.cycles if type(result.cycles) is int and 0 <= result.cycles <= 10000 else None,
               "error_code": result.error_code if result.error_code in (
                   None, "SERVICE_CONFIG_INVALID", "SERVICE_WORKER_FAILED") else "UNCLASSIFIED"}
        detail = result.failure_detail
        if type(detail) is dict:
            row["failure_detail"] = {
                key: detail.get(key) if type(detail.get(key)) is str and detail.get(key) in allowed
                else "UNCLASSIFIED"
                for key, allowed in (("stage", _FAILURE_STAGES), ("kind", _FAILURE_KINDS),
                                     ("reason", _FAILURE_REASONS))
            }
        safe.append(row)
    return json.dumps({"worker_started": started.is_set(), "adapter_entered": entered.is_set(),
                       "worker_finished": finished.is_set(), "worker_alive": thread.is_alive(),
                       "results": safe, "worker_stack": stack}, sort_keys=True)
