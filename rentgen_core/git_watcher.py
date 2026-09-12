"""Bounded orchestration for committed Git analysis and durable findings."""

from dataclasses import asdict
from pathlib import Path

from .errors import CoreError
from .git_observer import FindingReport, observe_git


def _option(value, name):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 4096
        or not value.strip()
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise CoreError("GIT_WATCHER_INVALID", f"Invalid {name}")
    return value


class GitWatcher:
    """Run one explicit, race-checked analysis pass for a committed HEAD.

    The caller owns the analyzer. It receives the immutable observation returned
    by observe_git and must return a complete FindingReport for the exact same
    observation, profile and scope. The watcher never starts a process, model,
    network request or background thread.
    """

    def __init__(
        self,
        observer,
        analyzer,
        *,
        repository=None,
        profile_id="analyzer-v1",
        scope_id="whole-repository",
    ):
        if not callable(analyzer):
            raise CoreError("GIT_WATCHER_INVALID", "Analyzer callback is required")
        self.observer = observer
        self.analyzer = analyzer
        self.repository = None if repository is None else Path(repository).resolve()
        self.profile_id = _option(profile_id, "profile_id")
        self.scope_id = _option(scope_id, "scope_id")

    def _report(self, observation):
        report = self.analyzer(observation)
        if not isinstance(report, FindingReport):
            raise CoreError(
                "GIT_WATCHER_CONTEXT", "Analyzer must return a FindingReport"
            )
        if (
            report.observation != observation
            or report.profile_id != self.profile_id
            or report.scope_id != self.scope_id
            or report.complete is not True
        ):
            raise CoreError(
                "GIT_WATCHER_CONTEXT",
                "Analyzer report is not bound to the observed commit",
            )
        return report

    @staticmethod
    def _state_commit(state, profile_id, scope_id):
        if state is None:
            return None
        report = state.get("report") if isinstance(state, dict) else None
        observation = report.get("observation") if isinstance(report, dict) else None
        if not isinstance(report, dict) or not isinstance(observation, dict):
            raise CoreError(
                "GIT_WATCHER_CONTEXT", "Durable findings state is malformed"
            )
        if report.get("profile_id") != profile_id or report.get("scope_id") != scope_id:
            raise CoreError(
                "GIT_WATCHER_CONTEXT",
                "Durable findings state belongs to another analysis context",
            )
        return observation.get("commit")

    def tick(self):
        """Analyze at most one new clean commit and persist it atomically."""
        with self.observer.locked():
            ctx = self.observer._context(write=True)
            self.observer._validate(ctx)
            repository = self.repository or ctx.source_root.resolve()
            expected = str(ctx.source_root.resolve())
            if str(repository) != expected:
                raise CoreError(
                    "GIT_WATCHER_CONTEXT",
                    "Repository must match the registered project source root",
                )
            observation = observe_git(repository)
            if observation.repository != expected:
                raise CoreError(
                    "GIT_WATCHER_CONTEXT",
                    "Repository must match the registered project source root",
                )

            status = self.observer.findings_status(limit=1)
            commit = self._state_commit(status["state"], self.profile_id, self.scope_id)
            if commit == observation.commit:
                return {
                    "status": "unchanged",
                    "commit": observation.commit,
                    "observation": asdict(observation),
                }

            report = self._report(observation)
            latest = observe_git(repository)
            if latest != observation:
                raise CoreError(
                    "GIT_HEAD_CHANGED",
                    "Git HEAD changed while the commit was being analyzed",
                )
            receipt = self.observer.record_findings(report, _locked=True)
            return {
                "status": "analyzed",
                "commit": observation.commit,
                "observation": asdict(observation),
                "receipt": receipt,
            }
