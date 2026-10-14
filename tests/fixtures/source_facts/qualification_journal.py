"""Bounded diagnostic progress for the pinned, supervised pytest invocation.

Only fixed test identities, phases, outcomes and measured times are recorded.
No captured output, assertion details, fixture data or source bytes are copied.
This journal never supplies acceptance counts or replaces complete JUnit evidence.
"""
import json
from pathlib import Path
import time

import pytest


MAX_JOURNAL_BYTES = 1024 * 1024


class QualificationJournal:
    def __init__(self, stream):
        self.stream = stream
        self.bytes_written = 0
        self.sequence = 0
        self.started = time.monotonic()
        self.failed = False

    def record(self, event, **fields):
        if self.failed:
            raise RuntimeError("Qualification progress journal already failed")
        try:
            self._record(event, **fields)
        except BaseException:
            self.failed = True
            raise

    def _record(self, event, **fields):
        now = time.monotonic()
        raw = (json.dumps({"sequence": self.sequence, "event": event,
                          "monotonic_seconds": now, "elapsed_seconds": now - self.started,
                          **fields}, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        if self.bytes_written + len(raw) > MAX_JOURNAL_BYTES:
            raise RuntimeError("Qualification progress journal bound exceeded")
        if self.stream.write(raw) != len(raw):
            raise OSError("Incomplete qualification progress journal write")
        self.stream.flush()
        self.bytes_written += len(raw)
        self.sequence += 1

    def pytest_sessionstart(self, session):
        self.record("session_start")

    def pytest_collection_finish(self, session):
        self.record("collection_finish", collected=len(session.items))

    def pytest_runtest_logstart(self, nodeid, location):
        self.record("item_start", nodeid=nodeid)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item):
        self.record("phase_start", nodeid=item.nodeid, phase="setup")
        yield

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_call(self, item):
        self.record("phase_start", nodeid=item.nodeid, phase="call")
        yield

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_teardown(self, item, nextitem):
        self.record("phase_start", nodeid=item.nodeid, phase="teardown")
        yield

    def pytest_runtest_logreport(self, report):
        self.record("phase_finish", nodeid=report.nodeid, phase=report.when,
                    outcome=report.outcome, duration_seconds=report.duration)

    def pytest_runtest_logfinish(self, nodeid, location):
        self.record("item_finish", nodeid=nodeid)

    def pytest_sessionfinish(self, session, exitstatus):
        self.record("session_finish", exitstatus=int(exitstatus))


def run_pytest(journal_path, args):
    # Exclusive creation preserves earlier evidence; unbuffered writes survive
    # an outer SIGKILL without requiring pytest/session/JUnit finalization.
    # Every open/write/flush/close error remains fatal to the pytest process.
    with Path(journal_path).open("xb", buffering=0) as stream:
        journal = QualificationJournal(stream)
        status = pytest.main(args, plugins=[journal])
        if journal.failed:
            raise RuntimeError("Qualification progress journal failed")
        return status
