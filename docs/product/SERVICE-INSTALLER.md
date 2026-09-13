# Windows SCM installer adapter proof

`rentgen_core.service_installer` adds explicit planning and bounded execution of
local `sc.exe` commands. This is an **adapter/installer proof**, not production
Windows service deployment. No real service installation was performed for this
proof; unit tests use injected executors and placeholder executable files.

The executable must already implement the native Windows service contract
(`ServiceMain`, dispatcher registration and control callbacks) in the actual
process started by SCM. `rentgen_core.service_entry` now provides that ctypes
boundary and a source Observer worker; its config and lifecycle contracts are
documented in [SERVICE-HOST.md](SERVICE-HOST.md). `WindowsServiceHost` remains
the separate foreground Git scheduler lifetime.

The installed `rentgen-service` console entry point proves CLI packaging only.
Its pip-generated EXE can launch a child Python process; this is not evidence
that SCM will connect to the correct dispatcher process. Do not substitute that
launcher for the placeholder executable below without validating a same-process
service image. The installer supports a strictly fixed direct-interpreter
ImagePath as described below, alongside its existing native EXE grammar. It does
not build or verify a native wrapper. Interpreter integrity, service ACLs,
signing, recovery policies and live deployment acceptance remain open; no
production acceptance is claimed here.

## API and plan

```python
from rentgen_core.service_installer import (
    ServiceInstallSpec,
    WindowsServiceInstaller,
)

spec = ServiceInstallSpec(
    service_name="Rentgen.Observer",
    display_name="Rentgen Observer",
    executable=r"C:\Rentgen\observer-service.exe",
    arguments=("--service", "--config", r"C:\Rentgen\settings.json"),
)
installer = WindowsServiceInstaller(timeout=15)
plan = installer.install(spec, start=True, dry_run=True)
# Equivalent: installer.plan("install", spec, start=True)
# Inspect plan.commands and the conditional plan.rollback.
# Explicit execution, only in an authorized deployment environment:
# installer.install(spec, start=True)
```

For the Python implementation, use the actual installed interpreter executable
and this exact argument tuple:

```python
spec = ServiceInstallSpec(
    service_name="Rentgen.Observer",
    display_name="Rentgen Observer",
    executable=r"C:\Python311\python.exe",
    arguments=(
        "-I", "-m", "rentgen_core.service_entry", "--service", "--config",
        r"C:\Rentgen\settings.json",
    ),
)
plan = installer.install(spec, start=True, dry_run=True)
# ImagePath: "C:\Python311\python.exe" -I -m rentgen_core.service_entry --service --config C:\Rentgen\settings.json
```

The supplied executable basename and its canonical target basename must each be
`python.exe` or `pythonw.exe` (case-insensitive). Exactly six arguments are
required, including the config path. Other modules, interpreter flags, `-c`,
`--console`, missing/extra/reordered arguments and the short native grammar are
rejected for these interpreter names. Other executable names cannot use this
Python grammar. The config path undergoes the same existence, canonicalization
and public-path validation as the native grammar; its contents are never read.

This ImagePath asks SCM to start the interpreter directly, where `-m` executes
the service module in that interpreter process. It bypasses the pip console
launcher. `-I` excludes the working directory and user site from the import path
and ignores Python environment settings, so the package must be installed in
the selected interpreter's ordinary site-packages. These Python behaviors are
documented in the [command-line reference](https://docs.python.org/3/using/cmdline.html#cmdoption-I).
Isolated mode does not establish trust in installed packages or their startup
hooks. The basename check does not establish that a supplied executable is a
genuine interpreter instead of a renamed program or redirecting launcher.
Verify the deployed executable and its process behavior independently.

Install and update use the entire quoted ImagePath in one existing `sc create`
or `sc config` call. Update preserves account/type and performs no restart.
Direct-interpreter tests use placeholder files and fake executors; live SCM
RUNNING/STOPPED, LocalService access, stop during a tick and recovery behavior
remain acceptance work in an explicitly authorized deployment environment.

Names, executable and argument tuples are immutable. Plans contain immutable
argv tuples and are deterministic for a spec and installer. Dry-run runs no
subprocess and contacts no SCM. Spec construction checks file metadata; dry-run
is not a filesystem-free operation. Offline planning is allowed on non-Windows;
all execution, even with an injected executor, fails closed on non-Windows.

The installer uses `%SystemRoot%\System32\sc.exe`, without a PATH search or a
PowerShell alias. The optional `sc_executable` overrides the local executable for
controlled embedding/testing. The environment and injected executor are trusted
caller inputs, not a remote configuration interface. Execution requires that
SCM executable to exist; access denial and SCM failures never permit subsequent
mutations. Install/update revalidate the referenced files during preflight before
the first SCM query. An already-created spec remains usable for query/start/stop/uninstall
if the service binary has subsequently disappeared.

## Input and IO bounds

- Service name: 1–80 ASCII letters, digits, `_`, `.`, `-`; starts with a letter.
- Display name: 1–120 characters; word characters, spaces, `.`, `(`, `)`, `-`.
- Existing local absolute `.exe` path; optional existing local absolute `.json`
  config path; each path is at most 240 characters and resolved canonically.
- Arguments are an immutable tuple. Native EXEs retain the existing grammar of
  at most three strings: optional `--service`, followed by optional
  `--config <path>`. `python.exe`/`pythonw.exe` require exactly six strings:
  `-I -m rentgen_core.service_entry --service --config <path>`. There is no
  arbitrary module, argument, password, token, account, environment or shell
  channel. The executable is always quoted; argument quoting uses Windows CRT
  escaping and the existing deterministic `binary_path` representation.
- Control characters, CR/LF, credential markers, UNC/device paths, alternate
  streams, traversal, shell expansion and invalid path characters are rejected.
- Config contents are never opened by this adapter. Callers must treat names and
  paths as public metadata; validation cannot recognize an arbitrary opaque
  secret disguised as a filename/name. Put credentials in protected storage,
  never in these public fields. Credential-like input raises a generic error
  without echoing the value.
- Every subprocess receives a list, `shell=False`, closed stdin, discarded stdout
  and stderr, and a finite timeout in `(0, 60]` seconds (default 15). Output cannot
  accumulate in memory or temporary files. No raw subprocess output or exception
  text enters results. The injected executor must honor these same limits.

## Operation ordering and partial outcomes

| Operation | Ordered commands | Result and failure boundary |
| --- | --- | --- |
| install | query → create → optional start | Query must report absent (1060); create uses `type= own`, `start= demand`, and `NT AUTHORITY\LocalService`. Existing services are never overwritten. |
| update | query → config | Requires existing service; changes binary path, display name and demand startup in one config call. Existing account/type are preserved. No implicit restart or delete. |
| start | query → start | Requires existing service; submits one start request. |
| stop | query → stop | Requires existing service; submits one stop request. Already-stopped remains a typed error for this explicit operation. |
| uninstall | query → stop → delete | Requires existing service. Only stop success or already-stopped (1062) permits delete. |
| query/status | query | Read-only existence result (`exists=True/False`), accepting only success/absent (1060). No localized output parsing. |

`ServiceOperationResult` confirms command acceptance, not daemon health or a
completed RUNNING/STOPPED transition. Start/stop transitions are asynchronous;
there is no polling or retry. Delete can mark a service for later deletion while
it is running or another process holds an open handle. Therefore uninstall and
rollback return after the delete request, not confirmed physical removal.
Microsoft documents these semantics in
[sc delete](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-delete).
The command option/value separation follows
[sc create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create)
and [sc config](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-config).

SCM does not provide a transaction across these commands. After a successful
create, failure of the optional start triggers exactly one delete request for
the service created by this call. Error details report `rollback=delete_requested`
or `rollback=failed`; the original error is retained. A failed create, including
a timeout with unknown result, never triggers deletion. An operator must inspect
such an unknown outcome before another attempt. Update never rolls back by
deleting an existing service. No operation has blind retries.

The caller must serialize operations and exclude concurrent administration of
the same service name. This proof has no native service handle/ownership token
that could make compensation safe against external delete-and-recreate races.
Executable/config replacement races and ACL validation also require deployment
controls outside this adapter.

For `service_entry`, the config's `service_name` must equal the actual SCM name;
the entrypoint rejects a mismatch and additional SCM start arguments. Config
contents are loaded only inside ServiceMain's worker after dispatcher connection
and `START_PENDING`; installer validation still never reads those contents.
The default `LocalService` account needs its own project membership and an
Observer profile bound to that exact Windows process principal. The entrypoint
does not reuse an interactive user's identity, initialize/rebind profiles or
grant permissions during startup. Provisioning these resources is separate.

### Filesystem identity boundary (self-audit)

`_file` deliberately follows symlinks and resolvable Windows reparse points
(including directory junctions) to their canonical local target. It validates
both the supplied path and the resolved target, including suffix and forbidden
characters. It does not enumerate/reject every reparse tag or require a link
count of one: hardlinks are accepted. Executable/config paths in the spec and an
explicit `sc_executable` are stored canonically. The default SystemRoot SCM path
is validated at execution and retains its configured spelling.

These checks establish path validity and current file existence, not trusted
file identity. No file handle, inode identity, digest or protected directory
handle is retained between validation and SCM use. A local actor with write
access can replace a file, its hardlink contents or a directory/reparse target
after a check, including during the preflight SCM query. The installed binary
may also change before SCM eventually starts it. Revalidation is best effort;
this adapter does not claim TOCTOU protection or integrity of executables/config.
Restricting writes and service administration is the deployment owner's duty.

Unit tests exercise actual temporary-file hardlinks and mocked canonical
resolution for all three path inputs. Windows symlink creation privilege is
unavailable on the verification host, so these are resolver-contract tests,
not native symlink/junction acceptance evidence.

## Typed errors and evidence

All validation/SCM errors use `CoreError`. Codes include `SERVICE_SPEC_INVALID`,
`SERVICE_PLATFORM_UNSUPPORTED`, `SERVICE_SCM_UNAVAILABLE`, `SERVICE_SCM_TIMEOUT`,
`SERVICE_SCM_PROTOCOL`, `SERVICE_SCM_FAILED`, and `SERVICE_ALREADY_EXISTS`.
Only numeric return codes, fixed command verbs and rollback outcome labels are
included in error details. Timeouts explicitly report an unknown command outcome.

Focused verification (no live SCM mutation):

```text
python -m pytest tests/unit/test_service_entry.py tests/unit/test_service_installer.py tests/unit/test_service_host.py -q
python -m black --check rentgen_core/service_entry.py tests/unit/test_service_entry.py rentgen_core/service_installer.py tests/unit/test_service_installer.py
python -m ruff check rentgen_core/service_entry.py tests/unit/test_service_entry.py rentgen_core/service_installer.py tests/unit/test_service_installer.py
git diff --check
```
