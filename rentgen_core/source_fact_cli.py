"""Command-local non-echoing boundary; legacy CLI error behavior is unchanged."""
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
from uuid import uuid4

from .errors import CoreError
from .source_fact_process import failure
from .source_fact_schema import UINT

_CODES = frozenset("SOURCE_FACTS_" + name for name in """INVALID_ARGUMENT CAPABILITY_UNAVAILABLE
PERMISSION_DENIED ACCESS_UNAVAILABLE INPUT_REJECTED ENTRY_NOT_FOUND EXECUTABLE_INVALID
READ_LIMIT CANCELLED TIMEOUT LAUNCH_FAILED HANDSHAKE_INVALID PROTOCOL_INVALID CHILD_FAILED
OUTPUT_LIMIT RECEIPT_INVALID CLEANUP_UNCONFIRMED INTERNAL_ERROR""".split())


def public_error(error, *, admission=False):
    if isinstance(error, KeyboardInterrupt):
        return failure("CANCELLED")
    if isinstance(error, CoreError):
        if error.code in _CODES:
            return failure(error.code.removeprefix("SOURCE_FACTS_"))
        mapped = {"PROJECT_FORBIDDEN": "PERMISSION_DENIED", "INVALID_ARGUMENT": "INVALID_ARGUMENT",
                  "CAPABILITY_UNAVAILABLE": "CAPABILITY_UNAVAILABLE", "OUTPUT_LIMIT_EXCEEDED": "OUTPUT_LIMIT"}
        if error.code in mapped:
            return failure(mapped[error.code])
    return failure("ACCESS_UNAVAILABLE" if admission else "INTERNAL_ERROR")


def run_source_cli(argv, *, invalid_placement=False):
    # Imported only after cli.main has selected this command, avoiding a cycle.
    from . import cli
    from .submitted_source_facts import authorize

    request_id = str(uuid4())
    scope = cli._ProposalScope()
    deadline = time.monotonic() + 60
    cancel_requested = False
    cancelled = lambda: cancel_requested
    write_started = False
    old_handler = None
    installed_handler = False
    phase = "arguments"

    def check():
        if scope.context is not None:
            authorize(scope.context)
        if cancelled():
            raise failure("CANCELLED")
        if time.monotonic() >= deadline:
            raise failure("TIMEOUT")

    def write_error(error):
        error = public_error(error, admission=phase == "admission" and scope.context is None)
        # Only these fixed strings and our generated UUID reach the fallback.
        # It is also safe if serialization itself was the interrupted phase.
        def encode(item):
            return ('{"error":{"code":"%s","message":"Submitted source facts could not be completed",'
                    '"request_id":"%s","details":{}}}') % (item.code, request_id)
        encoded = encode(error)
        if error.code != "SOURCE_FACTS_CLEANUP_UNCONFIRMED":
            try:
                check()
            except BaseException as final_error:
                if isinstance(final_error, (KeyboardInterrupt, Exception)):
                    encoded = encode(public_error(final_error, admission=True))
                else:
                    encoded = encode(failure("INTERNAL_ERROR"))
        try:
            print(encoded, flush=True)
        except BaseException:
            quiet_output_failure()

    def quiet_output_failure():
        # Prevent a second interpreter-finalization flush of a broken real
        # stdout pipe from printing a dynamic "Exception ignored" diagnostic.
        # Fake/captured streams with other descriptors are not modified.
        try:
            if sys.stdout.fileno() == 1:
                fd = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(fd, 1)
                finally:
                    os.close(fd)
        except BaseException:
            pass

    def request_cancel(*_):
        nonlocal cancel_requested
        # Python signal handlers can nest. A bool store avoids Event/Condition
        # locks that a second SIGINT could interrupt and deadlock.
        cancel_requested = True

    try:
        if threading.current_thread() is threading.main_thread():
            old_handler = signal.getsignal(signal.SIGINT)
            # A second SIGINT cannot interrupt owned-child cleanup/reap.
            signal.signal(signal.SIGINT, request_cancel)
            installed_handler = True
        if invalid_placement:
            raise failure("INVALID_ARGUMENT")
        if any(value in {"-h", "--help"} for value in argv[1:]):
            if argv not in (["source-facts", "--help"], ["source-facts", "-h"]):
                raise failure("INVALID_ARGUMENT")
            try:
                cli._parser().parse_args(argv)
            except SystemExit as error:
                if error.code == 0:
                    return 0
                raise failure("INVALID_ARGUMENT") from None
        try:
            args = cli._parser().parse_args(argv)
        except (CoreError, ValueError, TypeError, SystemExit):
            raise failure("INVALID_ARGUMENT") from None
        for name in ("selector_start", "selector_end"):
            value = getattr(args, name)
            if type(value) is not str or UINT.fullmatch(value) is None or len(value) > 6 or int(value) > 524_288:
                raise failure("INVALID_ARGUMENT")
            setattr(args, name, int(value))
        for name in ("registry", "identity_profile", "archive", "input_core", "source_scanner", "source_kernel"):
            value = getattr(args, name)
            if value is not None and (not Path(value).is_absolute() or ".." in Path(value).parts):
                raise failure("INVALID_ARGUMENT")
        check()
        args._source_cancelled = cancelled
        args._source_deadline = deadline
        phase = "admission"
        result = cli._execute(args, proposal_scope=scope)
        phase = "serialization"
        if not isinstance(result, cli._ProposalCommandResult) or result.context is not scope.context:
            raise failure("INTERNAL_ERROR")
        encoded = json.dumps({"result": result.value, "request_id": request_id},
                             ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 65_536 or result.output_limit != 65_536:
            raise failure("OUTPUT_LIMIT")
        check()
        write_started = True
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(encoded + b"\n")
            sys.stdout.buffer.flush()
        else:
            print(encoded.decode("utf-8"), flush=True)
        return 0
    except BaseException as error:
        # The source workflow closes/reaps its context-owned children before any
        # exception reaches this outer disclosure boundary.
        if write_started:
            # A receiver must discard a partial success at exit 2. Never append
            # an error JSON or expose the failed transport's exception text.
            quiet_output_failure()
        elif isinstance(error, (KeyboardInterrupt, Exception)):
            write_error(error)
        else:
            write_error(failure("INTERNAL_ERROR"))
        return 2
    finally:
        if installed_handler:
            try:
                signal.signal(signal.SIGINT, old_handler)
            except BaseException:
                return 2
