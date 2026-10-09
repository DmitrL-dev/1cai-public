"""Experimental handwritten-source mechanics, with no binding/runtime finding."""
import base64
import json
from pathlib import Path
import sqlite3
import sys
import time

from .errors import CoreError
from .rust_input import RustInputSession
from .source_fact_process import checkpoint, failure, run_owned_helper
from .source_fact_schema import (
    HASH, identifier, make_kernel_envelope, validate_kernel, validate_scan,
    xml_observations,
)

PERMISSIONS = frozenset({"project:read", "analysis:run"})


def authorize(ctx):
    try:
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(PERMISSIONS)
    except CoreError as error:
        raise failure("PERMISSION_DENIED" if error.code == "PROJECT_FORBIDDEN" else "ACCESS_UNAVAILABLE") from None
    except (OSError, sqlite3.Error):
        raise failure("ACCESS_UNAVAILABLE") from None


def _reference(entry):
    return {"entry_id": entry["entry_id"], "relative_path": entry["path"],
            "size_bytes": entry["size_bytes"], "raw_sha256": entry["raw_sha256"]}


def source_facts(ctx, *, archive, archive_sha256, input_core, input_core_sha256,
                 source_scanner, source_scanner_sha256, source_kernel,
                 source_kernel_sha256, caller_entry, candidate_entry,
                 selector_start, selector_end, cancelled=None, deadline=None):
    deadline = min(deadline, time.monotonic() + 60) if deadline is not None else time.monotonic() + 60
    check = lambda: checkpoint(lambda: authorize(ctx), cancelled, deadline)
    check()
    if sys.platform != "linux":
        raise failure("CAPABILITY_UNAVAILABLE")
    for value in (archive_sha256, input_core_sha256, source_scanner_sha256, source_kernel_sha256):
        if type(value) is not str or HASH.fullmatch(value) is None:
            raise failure("INVALID_ARGUMENT")
    for value in (archive, input_core, source_scanner, source_kernel):
        if not Path(value).is_absolute() or ".." in Path(value).parts:
            raise failure("INVALID_ARGUMENT")
    if (type(caller_entry) is not str or not caller_entry.endswith(".bsl")
            or type(candidate_entry) is not str):
        raise failure("INVALID_ARGUMENT")
    parts = candidate_entry.split("/")
    if (len(parts) != 4 or parts[0] != "CommonModules" or parts[2:] != ["Ext", "Module.bsl"]
            or not identifier(parts[1])):
        raise failure("INVALID_ARGUMENT")
    if any(type(v) is not int or not 0 <= v <= 524_288 for v in (selector_start, selector_end)):
        raise failure("INVALID_ARGUMENT")
    metadata_path = "CommonModules/" + parts[1] + ".xml"
    selection = {"start": selector_start, "end": selector_end}
    buffers = {}
    try:
        with RustInputSession(input_core, input_core_sha256, authorize=check, checkpoint=check) as session:
            session.deadline = min(session.deadline, deadline)
            manifest = session.open_import(archive, archive_sha256)
            entries = session.entries(manifest)
            index = {entry["path"]: entry for entry in entries}
            if caller_entry not in index or candidate_entry not in index:
                raise failure("ENTRY_NOT_FOUND")
            caller, candidate = index[caller_entry], index[candidate_entry]
            metadata = index.get(metadata_path)
            total = 0
            for entry in (caller, candidate, metadata):
                if entry is None or entry["entry_id"] in buffers:
                    continue
                check()
                if entry is not metadata and entry["size_bytes"] > 524_288:
                    raise failure("READ_LIMIT")
                total += entry["size_bytes"]
                if total > 8_388_608:
                    raise failure("READ_LIMIT")
                buffers[entry["entry_id"]] = session.read_entry(entry)
                check()
    except CoreError as error:
        if error.code.startswith("SOURCE_FACTS_"):
            raise
        if error.code == "INPUT_CORE_CLEANUP_UNCONFIRMED":
            raise failure("CLEANUP_UNCONFIRMED") from None
        if error.code in {"INPUT_CORE_EXECUTABLE_INVALID", "INPUT_CORE_INVALID_ARGUMENT"}:
            raise failure("EXECUTABLE_INVALID") from None
        raise failure("INPUT_REJECTED") from None
    except OSError:
        raise failure("INPUT_REJECTED") from None
    # Input-core is fully reaped here. Only verified immutable Python bytes
    # remain; at most one new helper is owned during either later exchange.
    check()

    def buffer(entry):
        return {"entry_id": entry["entry_id"], "size_bytes": entry["size_bytes"],
                "raw_sha256": entry["raw_sha256"],
                "data_base64": base64.b64encode(buffers[entry["entry_id"]]).decode("ascii")}

    request = {"protocol": "source_fact_scan_v1", "caller": buffer(caller),
               "candidate": {"kind": "same_as_caller"} if caller is candidate else
               {"kind": "distinct_entry", "buffer": buffer(candidate)},
               "selection": selection}
    encode = lambda value: json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    scan_raw = run_owned_helper(source_scanner, source_scanner_sha256,
                                role="scanner", request=encode(request),
                                authorize=lambda: authorize(ctx), cancelled=cancelled,
                                deadline=deadline)
    check()
    scan, receiver_name = validate_scan(scan_raw, caller, candidate, buffers, selection)
    check()
    xml_name, server = xml_observations(None if metadata is None else buffers[metadata["entry_id"]])
    check()
    envelope = make_kernel_envelope(scan, receiver_name, parts[1], xml_name, server,
                                    caller=caller, candidate=candidate, metadata=metadata)
    # A private invocation-local receipt map. It is not serialized or persisted.
    # The Go spans and XML expanded property bind observations to these bytes.
    ledger = {}
    roles = {"selector": caller, "export": candidate, "server": metadata}
    for role, receipt in envelope["receipts"].items():
        if receipt is None:
            continue
        entry = roles[role]
        if entry is None or receipt["entry_id"] != entry["entry_id"] + 1:
            raise failure("RECEIPT_INVALID")
        ledger[receipt["receipt_id"]] = {
            "scope": dict(envelope["scope"]), "input_sha256": archive_sha256,
            "entry": _reference(entry),
            "images": {"input_core": input_core_sha256, "source_scanner": source_scanner_sha256,
                       "source_kernel": source_kernel_sha256},
            "location": scan[role if role == "selector" else "header"] if role != "server"
            else tuple("{http://v8.1c.ru/8.3/MDClasses}" + part
                       for part in ("MetaDataObject", "CommonModule", "Properties", "Server")),
        }
    if len(ledger) != sum(v is not None for v in envelope["receipts"].values()):
        raise failure("RECEIPT_INVALID")
    kernel_raw = run_owned_helper(source_kernel, source_kernel_sha256,
                                  role="kernel", request=encode(envelope),
                                  authorize=lambda: authorize(ctx), cancelled=cancelled,
                                  deadline=deadline)
    check()
    kernel = validate_kernel(kernel_raw, envelope)
    check()
    return {
        "schema": 1, "scope": "submitted_source_facts",
        "workflow": "verified_bytes_to_source_facts_v1",
        "configuration_membership": "unverified", "configuration_completeness": "unverified",
        "xml_profile": "handwritten_common_module_properties_v1", "input_sha256": archive_sha256,
        "images": {"input_core": input_core_sha256, "source_scanner": source_scanner_sha256,
                   "source_kernel": source_kernel_sha256},
        "references": {"caller": _reference(caller), "candidate": _reference(candidate),
                       "metadata": None if metadata is None else _reference(metadata)},
        "admission": {"caller": scan["caller"]["admission"], "candidate": scan["candidate"]["admission"]},
        "locations": {"selector": scan["selector"] if envelope["observations"]["selector"]["state"] == "observed" else None,
                      "export": scan["header"] if envelope["observations"]["export"]["state"] == "observed" else None},
        "kernel": kernel,
    }
