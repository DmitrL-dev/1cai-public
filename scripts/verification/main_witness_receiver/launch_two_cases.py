"""Root-only prospective SOURCE: two fresh synthetic HELLO/ACK hosts.
Author has not executed/imported/compiled this Source. Root precreates two
private case directories/seeds and pins this launcher, the verifier, all
native/Sender/fixture/security inputs, and the exact admission before effects.
The Root frozen() implementation below is copied byte-for-byte from the
accepted two-host launcher. A JSON receipt is never live native authority.
"""
from pathlib import Path
import argparse, ctypes, hashlib, json, os, subprocess, sys, threading, time
from ctypes import wintypes as W

# The operator-owned evidence root is explicitly bound below by CLI and admission.
CASES = ("expected_parent_slot0", "expected_child_slot1")
INPUT_KEYS = ("C", "header", "base_header", "dll", "node", "parent", "child")
APPROVED_SOURCE = {
    "C": (75900, "fe81974981d4ab20156814d1dfae6f90610cabb8f5a0fff0cebcbd49c3a8e16e"),
    "header": (5622, "92869b7a616198fbf8f6beb83f074e9e82df3a3cf000bbd454e0868248bef280"),
    "base_header": (6141, "b14f94f5674ec55b2f8fc15900bb63e5b466ce21406042c6c204bdefae84328c"),
    "node": (91694408, "3331e1ffe19874215472217c5e94f5a0c6d8e18c4ac7111d3937aa0ad5e9b4a5"),
    "parent": (5294, "11015fc699e645f927f286b55db743cfaedf020eff60a39426b2b3ff6527118f"),
    "child": (43, "5748b8d4f8bc52c6871ccf135e0fda61670a8e69c0567ff9419afcfac3476411")}
HOST_TIMEOUT, STDIO_CAP, RESULT_CAP = 15, 8192, 196608
slots, cases, close_errors, retained = [], [], [], []

def need(ok, why):
    if not ok:
        raise RuntimeError(why)

def summary_error(exc):
    return {"type": type(exc).__name__, "message": str(exc)[:1024]}

def absolute(value):
    need(type(value) is str and value, "absolute path")
    p = Path(value)
    need(p.is_absolute() and len(p.drive) == 2 and p.drive[1] == ":" and
         not str(p).startswith("\\\\"), "drive-rooted path")
    return p

def pin(p, cap=128 * 1024 * 1024):
    h, size = hashlib.sha256(), 0
    with p.open("rb") as f:
        while True:
            part = f.read(65536)
            if not part:
                break
            size += len(part)
            need(size <= cap, "pinned file cap")
            h.update(part)
    return {"path": str(p), "size_bytes": size, "sha256": h.hexdigest()}

def checked_ref(ref, cap=128 * 1024 * 1024):
    need(type(ref) is dict and set(ref) == {"path", "size_bytes", "sha256"}, "ref fields")
    p = absolute(ref["path"])
    need(type(ref["size_bytes"]) is int and 0 < ref["size_bytes"] <= cap and
         type(ref["sha256"]) is str and len(ref["sha256"]) == 64 and
         all(c in "0123456789abcdef" for c in ref["sha256"]), "ref values")
    need(pin(p, cap) == ref, "exact input pin")
    return p

def strict_json(raw):
    def pairs(items):
        d = {}
        for key, value in items:
            need(key not in d, "duplicate retained JSON key")
            d[key] = value
        return d
    def bad(value):
        raise ValueError("nonfinite/noninteger retained JSON")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_float=bad, parse_constant=bad)

def read_json(ref, cap):
    p = checked_ref(ref, cap)
    with p.open("rb") as f:
        raw = f.read(cap + 1)
    need(len(raw) <= cap, "JSON read cap")
    return strict_json(raw)

def put(p, value):
    raw = (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    need(len(raw) <= 1048576, "launcher retained JSON cap")
    with p.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return pin(p, 1048576)

def frozen_view():
    return [{key: value for key, value in s.items() if key != "handle"} for s in slots]

ap = argparse.ArgumentParser()
ap.add_argument("--evidence-root", required=True)
ap.add_argument("--admission", required=True)
ap.add_argument("--admission-size", required=True, type=int)
ap.add_argument("--admission-sha", required=True)
cli = ap.parse_args()
B = absolute(cli.evidence_root)
need(B.is_dir(), "existing operator-owned evidence root")
need(os.name == "nt" and sys.maxsize > 2**32 and sys.flags.optimize == 0 and
     sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
     "Windows x64/unoptimized Root runtime")
admission_path = absolute(cli.admission)
admission_ref = {"path": str(admission_path), "size_bytes": cli.admission_size,
                 "sha256": cli.admission_sha}
admission = read_json(admission_ref, 1048576)
need(type(admission) is dict and set(admission) ==
     {"schema", "Root_execution_admitted", "launcher", "verifier", "python",
      "inputs", "case_seeds", "additional_frozen_inputs", "owned_directory", "evidence_root", "outer_helper"} and
     admission["schema"] == "rentgen-Root-Main-receiver-two-hosts-execution-admission/2" and
     admission["Root_execution_admitted"] is True, "exact Root admission schema")
need(absolute(admission["evidence_root"]) == B, "exact operator-owned root admission")
launcher = checked_ref(admission["launcher"], 131072)
verifier = checked_ref(admission["verifier"], 131072)
python = checked_ref(admission["python"])
need(launcher == Path(__file__) and python == Path(sys.executable), "admitted host Sources/images")
need(type(admission["inputs"]) is dict and tuple(sorted(admission["inputs"])) ==
     tuple(sorted(INPUT_KEYS)), "admitted original input set")
input_paths = {key: checked_ref(admission["inputs"][key]) for key in INPUT_KEYS}
for key, expected in APPROVED_SOURCE.items():
    ref = admission["inputs"][key]
    need((ref["size_bytes"], ref["sha256"]) == expected, "exact Source-approved input " + key)
need(type(admission["case_seeds"]) is dict and set(admission["case_seeds"]) == set(CASES),
     "exact two admitted case configurations")
need(type(admission["additional_frozen_inputs"]) is list and
     len(admission["additional_frozen_inputs"]) <= 16, "bounded additional security inputs")
extra_paths = [checked_ref(ref, 1048576) for ref in admission["additional_frozen_inputs"]]
outer_helper = checked_ref(admission["outer_helper"], 131072)
need(admission["outer_helper"] in admission["additional_frozen_inputs"] and outer_helper in extra_paths,
     "actual admitted outer helper is frozen with all ancestors")
D = absolute(admission["owned_directory"])
need(D.parent == B and D.is_dir(), "Root-precreated fresh private directory")
seeds, configs, config_refs, work = {}, {}, {}, {}
for ordinal, name in enumerate(CASES, 1):
    cfg = read_json(admission["case_seeds"][name], 16384)
    need(type(cfg) is dict and set(cfg) == {"schema", "case", "working_directory",
         "generation", "session_cookie", "receiver"} and
         cfg["schema"] == "rentgen-Root-Main-receiver-case-seed/1", "exact case seed")
    seed_path = absolute(admission["case_seeds"][name]["path"])
    directory = absolute(cfg["working_directory"])
    need(directory.parent == D and directory.name == name and directory.is_dir() and
         seed_path.parent == directory,
         "Root-precreated exact owned case paths")
    need(cfg["case"] == name and type(cfg["generation"]) is int and cfg["generation"] == ordinal and
         type(cfg["session_cookie"]) is int and 0 < cfg["session_cookie"] < 2**64, "exact Root case seed")
    receiver = cfg["receiver"]
    need(type(receiver) is dict and set(receiver) ==
         {"expected_slot", "sid_ref", "instance", "nonce", "run", "source_copy_pin"} and
         type(receiver["expected_slot"]) is int and receiver["expected_slot"] == ordinal - 1 and
         receiver["sid_ref"] in admission["additional_frozen_inputs"] and
         receiver["source_copy_pin"] == admission["inputs"]["parent"]["sha256"], "exact receiver seed")
    sid_path = checked_ref(receiver["sid_ref"], 68)
    with sid_path.open("rb") as sid_file:
        sid = sid_file.read(69)
    need(8 <= len(sid) <= 68 and sid[0] == 1 and sid[1] <= 15 and len(sid) == 8 + 4 * sid[1],
         "bounded binary SID; native independently checks actual current token")
    for token in ("instance", "nonce"):
        need(type(receiver[token]) is str and len(receiver[token]) == 32 and
             all(c in "0123456789abcdef" for c in receiver[token]), "receiver token")
    need(type(receiver["run"]) is str and 1 <= len(receiver["run"]) <= 128 and
         all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-" for c in receiver["run"]),
         "receiver run ASCII token")
    need(not any((directory / output).exists() for output in
         ("config.json", "result.json", "host.stdout", "host.stderr", "Root-host-raw-execution-before-checks.json",
          "Root-case-checks-retained.json")), "fresh output names; never retry")
    seeds[name], work[name] = cfg, directory
need(seeds[CASES[0]]["session_cookie"] != seeds[CASES[1]]["session_cookie"],
     "fresh original session cookies")
need(seeds[CASES[0]]["receiver"]["expected_slot"] == 0 and
     seeds[CASES[1]]["receiver"]["expected_slot"] == 1, "parent-positive/child-negative selection")
need(seeds[CASES[0]]["receiver"]["instance"] != seeds[CASES[1]]["receiver"]["instance"] and
     seeds[CASES[0]]["receiver"]["nonce"] != seeds[CASES[1]]["receiver"]["nonce"],
     "fresh receiver instance/nonce per actual host")
# All effecting calls below follow this exact, externally pinned Root admission.
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
k.GetHandleInformation.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];k.GetHandleInformation.restype=W.BOOL
k.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD];k.GetFinalPathNameByHandleW.restype=W.DWORD
class ATTR(ctypes.Structure):_fields_=[('attributes',W.DWORD),('tag',W.DWORD)]
k.GetFileInformationByHandleEx.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.GetFileInformationByHandleEx.restype=W.BOOL

def frozen(p,directory):
 slot={'path':str(p),'kind':'directory' if directory else 'file','handle':None,'closed':False,'close_attempted':False};slots.append(slot)
 h=k.CreateFileW(str(p),0x80 if directory else 0x80000000,3 if directory else 1,None,3,(0x02000000|0x00200000) if directory else 0x00200000,None)
 if h in (None,ctypes.c_void_p(-1).value):raise RuntimeError('freeze-open:'+str(ctypes.get_last_error()))
 slot['handle']=h
 attr=ATTR();flags=W.DWORD();final=ctypes.create_unicode_buffer(2048)
 assert k.GetFileInformationByHandleEx(h,9,ctypes.byref(attr),ctypes.sizeof(attr)) and not (attr.attributes&0x400)
 assert bool(attr.attributes&0x10)==directory
 assert k.GetHandleInformation(h,ctypes.byref(flags)) and not(flags.value&1)
 n=k.GetFinalPathNameByHandleW(h,final,2048,0);assert 0<n<2048
 actual=final.value;assert actual.startswith('\\\\?\\') and actual[4:].rstrip('\\').casefold()==str(p).rstrip('\\').casefold()
 slot.update({'attributes':attr.attributes,'final_path':actual,'noninheritable':True,'share_delete':False,'share_write':directory,'share_read':True})

def run_owned_host(argv, directory, out_path, err_path):
    started = time.monotonic()
    end = started + HOST_TIMEOUT
    record = {"rc": None, "timed_out": False, "launch_error": None,
              "host_return_known": False, "stdio_producers_ended": False,
              "stdio_joined": False, "stdio_checked_closed": False, "own_host_kill_attempted": False}
    overflow = threading.Event()
    pumps, stream_records, files, proc = [], [], [], None
    retained.extend((record, overflow, pumps, stream_records, files))
    try:
        for path in (out_path, err_path):
            files.append(path.open("xb"))
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=False, close_fds=True,
                                cwd=directory, creationflags=0x08000000)
        retained.append(proc)  # owns ONLY the host created by this Popen
        def pump(stream, target, rec):
            rec["producer_started"] = True
            try:
                while True:
                    chunk = stream.read(4096)
                    rec["latest_chunk"] = chunk
                    if not chunk:
                        rec["EOF"] = True
                        break
                    rec["received_bytes"] += len(chunk)
                    remaining = max(0, STDIO_CAP - rec["retained_bytes"])
                    if remaining:
                        target.write(chunk[:remaining])
                        rec["retained_bytes"] += min(len(chunk), remaining)
                    if len(chunk) > remaining:
                        rec["overflow"] = True
                        overflow.set()
                    if time.monotonic() >= end:
                        rec["read_deadline_expired"] = True
                        break
            except BaseException as exc:
                rec["error"] = summary_error(exc)
                overflow.set()
            finally:
                rec["producer_ended"] = True
        for stream, target, label in zip((proc.stdout, proc.stderr), files, ("stdout", "stderr")):
            rec = {"label": label, "producer_started": False, "producer_ended": False,
                   "EOF": False, "received_bytes": 0, "retained_bytes": 0, "overflow": False,
                   "read_deadline_expired": False, "error": None, "latest_chunk": None,
                   "close_attempted": False, "closed": False}
            stream_records.append(rec)
            thread = threading.Thread(target=pump, args=(stream, target, rec), daemon=True)
            pumps.append((thread, stream, rec))
            retained.extend((pump, thread, stream, target, rec))
            thread.start()
        while proc.poll() is None:
            remaining = end - time.monotonic()
            if overflow.is_set() or remaining <= 0:
                record["timed_out"] = remaining <= 0
                record["own_host_kill_attempted"] = True
                proc.kill()  # one original Popen-owned host; no PID adoption
                break
            overflow.wait(min(0.01, remaining))
        record["rc"] = proc.wait(timeout=max(0.001, end - time.monotonic() + 0.30))
        record["host_return_known"] = True
        for thread, _, _ in pumps:
            thread.join(max(0.0, end + 0.30 - time.monotonic()))
        record["stdio_producers_ended"] = all(rec["producer_ended"] for rec in stream_records)
        record["stdio_joined"] = all(not thread.is_alive() for thread, _, _ in pumps)
        if record["stdio_producers_ended"] and record["stdio_joined"]:
            for _, stream, rec in pumps:
                rec["close_attempted"] = True
                try:
                    stream.close()
                    rec["closed"] = stream.closed
                except BaseException as exc:
                    rec["close_error"] = summary_error(exc)
            for target in files:
                target.flush()
                os.fsync(target.fileno())
                target.close()
            record["stdio_checked_closed"] = all(rec["closed"] for rec in stream_records) and all(f.closed for f in files)
    except BaseException as exc:
        record["launch_error"] = summary_error(exc)
    record["seconds"] = time.monotonic() - started
    record["stdio"] = [{key: value for key, value in rec.items() if key != "latest_chunk"}
                       for rec in stream_records]
    record["all_owned_producers_and_host_ended"] = (
        record["host_return_known"] and record["stdio_producers_ended"] and
        record["stdio_joined"] and record["stdio_checked_closed"])
    return record

primary = None
all_hosts_ended = True
freeze_ref = None
try:
    allfiles = list(input_paths.values()) + [verifier, python, admission_path, launcher] + extra_paths
    allfiles += [absolute(admission["case_seeds"][name]["path"]) for name in CASES]
    directories = set()
    for directory in list(work.values()) + [D] + [p.parent for p in allfiles]:
        directories.add(directory)
        directories.update(directory.parents)
    for directory in sorted(directories, key=lambda p: (len(p.parts), str(p).casefold())):
        frozen(directory, True)
    for path in dict.fromkeys(allfiles):
        frozen(path, False)
    need(read_json(admission_ref, 1048576) == admission, "frozen exact admission")
    for key in INPUT_KEYS:
        checked_ref(admission["inputs"][key])
    for key in ("launcher", "verifier", "python"):
        checked_ref(admission[key])
    for ref in admission["additional_frozen_inputs"]:
        checked_ref(ref, 1048576)
    for name in CASES:
        need(read_json(admission["case_seeds"][name], 16384) == seeds[name], "frozen seed bytes")
    pre_config_freeze = put(D / "Root-pre-config-input-peer-security-freeze.json", {
        "schema": "Root-Main-receiver-pre-config-input-freeze/1",
        "Root_execution_admission_ref": admission_ref, "admitted": admission,
        "frozen_path_slots": frozen_view(), "configs_not_yet_created": True,
        "EditorRole": False, "OwnerIPC": False,
        "runtime_qualified": False})
    frozen(Path(pre_config_freeze["path"]), False)
    for name in CASES:
        seed = seeds[name]
        cfg = {"schema": "rentgen-Root-Main-receiver-verifier-inputs/1", "case": name,
               "verifier": admission["verifier"], "python": admission["python"],
               **admission["inputs"], "working_directory": seed["working_directory"],
               "generation": seed["generation"], "session_cookie": seed["session_cookie"],
               "receiver": seed["receiver"],
               "Root_freeze_ref": pre_config_freeze, "Root_execution_admission_ref": admission_ref}
        configs[name] = cfg
        config_refs[name] = put(work[name] / "config.json", cfg)
        need(config_refs[name]["size_bytes"] <= 16384, "verifier config cap")
        frozen(Path(config_refs[name]["path"]), False)
    freeze_ref = put(D / "Root-all-inputs-configs-peer-security-frozen-before-hosts.json", {
        "schema": "Root-Main-receiver-exact-input-config-freeze/1",
        "Root_execution_admission_ref": admission_ref, "pre_config_freeze": pre_config_freeze,
        "configs": config_refs, "frozen_path_slots": frozen_view(),
        "EditorRole": False, "OwnerIPC": False, "runtime_qualified": False})
    frozen(Path(freeze_ref["path"]), False)
    for name in CASES:
        directory, result_path = work[name], work[name] / "result.json"
        out, err = directory / "host.stdout", directory / "host.stderr"
        argv = [str(python), "-I", "-S", "-B", str(verifier), "--case", name,
                "--config", config_refs[name]["path"], "--output", str(result_path)]
        all_hosts_ended = False
        execution = run_owned_host(argv, directory, out, err)
        all_hosts_ended = execution["all_owned_producers_and_host_ended"]
        record = {"schema": "Root-Main-receiver-host-execution-raw/1", "case": name,
                  "argv": argv, "timeout_seconds": HOST_TIMEOUT, **execution,
                  "config_ref": config_refs[name],
                  "freeze_ref": freeze_ref, "Root_execution_admission_ref": admission_ref,
                  "stdout_ref": pin(out, STDIO_CAP) if all_hosts_ended else None,
                  "stderr_ref": pin(err, STDIO_CAP) if all_hosts_ended else None,
                  "observed_result_size": result_path.stat().st_size if all_hosts_ended and result_path.is_file() else None,
                  "result_ref": pin(result_path, RESULT_CAP) if all_hosts_ended and result_path.is_file() and
                      result_path.stat().st_size <= RESULT_CAP else None,
                  "EditorRole": False, "OwnerIPC": False, "runtime_qualified": False}
        raw_ref = put(directory / "Root-host-raw-execution-before-checks.json", record)
        case = {"case": name, "raw_execution_ref": raw_ref, "accepted_synthetic_receiver_only": False}
        try:
            need(all_hosts_ended and execution["launch_error"] is None and
                 not execution["timed_out"] and not execution["own_host_kill_attempted"] and
                 execution["rc"] == 0 and all(not r["overflow"] and r["EOF"] and
                 not r["read_deadline_expired"] and r["error"] is None for r in execution["stdio"]),
                 "original host/stdio complete within cap/deadline")
            need(record["stderr_ref"]["size_bytes"] == 0 and record["result_ref"] is not None,
                 "complete bounded raw output")
            stdout = strict_json(out.read_bytes())
            actual = strict_json(result_path.read_bytes())
            need(stdout["result_ref"] == record["result_ref"] and
                 stdout["synthetic_case_passed"] is True and stdout["cleanup_observed_known"] is True and
                 stdout["runtime_qualified"] is False, "stdout/raw exact join")
            need(actual["case"] == name and actual["synthetic_case_passed"] is True and
                 actual["cleanup_observed_known"] is True and
                 actual["receiver_IO_producer_handle_retirement_observed_known"] is True and
                 actual["Python_worker_producer_ended"] is True and actual["Python_worker_joined"] is True and
                 all(call["producer_ended"] for call in actual["native_call_producers"]),
                 "receiver verifier completed; all original producers ended")
            terminal = actual["receiver_terminal_observation"]
            need(terminal["accepted"] == terminal["submit_done"] == 1 and
                 terminal["command_index"] == 2**64 - 1 and terminal["status"]["status_index"] == 2**32 - 1 and
                 terminal["call"] == {"entered": 1, "done": 1, "ok": 1, "error": 0},
                 "actual additive final-status receipt after native return/join")
            if name == "expected_child_slot1":
                need(actual["negative_native_first_P_preserved"] is True and
                     actual["negative_native_auto_stop_observed"] is True and actual["stop_attempted"] is False and
                     actual["run_call"] == {"entered": 1, "done": 1, "ok": 0, "error": 5},
                     "negative first-P/auto-stop distinct from positive run success")
            need(actual["inputs"] == {key: configs[name][key] for key in
                 INPUT_KEYS + ("verifier", "python", "Root_freeze_ref", "Root_execution_admission_ref")},
                 "exact original input refs")
            binding = actual["original_binding"]
            need(binding["generation"] == configs[name]["generation"] and
                 binding["session_cookie"] == configs[name]["session_cookie"] and
                 binding["run_ms"] == 4000 and binding["closure_ms"] == 2500,
                 "immutable original run/closure ends")
            need(all(actual[key] is False for key in
                 ("EditorRole", "OwnerIPC", "READY", "Core", "model", "native_1C", "release",
                  "runtime_qualified", "production_deployment")), "false grants")
            case["actual"] = actual
            case["accepted_synthetic_receiver_only"] = True
        except BaseException as exc:
            case["finding"] = summary_error(exc)
        case_ref = put(directory / "Root-case-checks-retained.json", case)
        cases.append(case_ref)
        print(json.dumps({"case": name, "raw": raw_ref, "checked": case_ref,
                          "accepted_synthetic_receiver_only": case["accepted_synthetic_receiver_only"]}), flush=True)
        need(case["accepted_synthetic_receiver_only"], "preserve failed case; never name retry")
except BaseException as exc:
    primary = summary_error(exc)
finally:
    if all_hosts_ended:
        for slot in reversed(slots):
            if slot["handle"] is None or slot["close_attempted"]:
                continue
            slot["close_attempted"] = True
            if k.CloseHandle(slot["handle"]):
                slot["closed"] = True
                slot["handle"] = None
            else:
                close_errors.append({"path": slot["path"], "error": ctypes.get_last_error()})
    summary = {"schema": "Root-Main-receiver-two-fresh-hosts-retained/1", "owned_directory": str(D),
               "cases": cases, "Root_execution_admission_ref": admission_ref, "freeze_ref": freeze_ref,
               "frozen_path_slots": frozen_view(), "all_hosts_and_stdio_known_ended": all_hosts_ended,
               "all_Root_freeze_handles_checked_closed": all_hosts_ended and
                   all(s["handle"] is None for s in slots) and not close_errors,
               "Root_close_errors": close_errors, "primary": primary,
               "accepted_synthetic_receiver_only": primary is None and len(cases) == 2 and
                   all_hosts_ended and all(s["handle"] is None for s in slots) and not close_errors,
               "EditorRole": False, "OwnerIPC": False, "READY": False, "Core_model_native1C_calls": 0,
               "runtime_qualified": False, "release": False, "production_deployment": False}
    exitcode = 2
    try:
        summary_ref = put(D / "Root-two-fresh-hosts-and-freeze-close-retained-result.json", summary)
        print(json.dumps({"retained": summary_ref,
                          "accepted_synthetic_receiver_only": summary["accepted_synthetic_receiver_only"]}), flush=True)
        exitcode = 0 if summary["accepted_synthetic_receiver_only"] else 2
    finally:
        # UNKNOWN retains original objects and freezes until this own host exit.
        # No numerical PID/handle retry, FreeLibrary, reset or false cleanup fact.
        os._exit(exitcode)
