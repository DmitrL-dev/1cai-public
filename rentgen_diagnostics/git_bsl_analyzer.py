"""Read-only BSL-LS analyzer for one exact committed Git observation."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess

from rentgen_core.errors import CoreError
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.diagnostics import BslAnalysis, BSL_PROFILE_ID


MAX_FILES = 256
MAX_FILE = 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
PROFILE_ID = BSL_PROFILE_ID + ":git-v1"
SCOPE_ID = "whole-repository-bsl"


def _valid_path(value):
    path = PurePosixPath(value)
    return (
        bool(value)
        and str(path) == value
        and not (
            path.is_absolute()
            or value == "."
            or ".." in path.parts
            or "\\" in value
            or ":" in value
            or any(ord(character) < 32 for character in value)
        )
    )


class BslGitAnalyzer:
    """Adapt trusted single-module BSL-LS execution to GitWatcher findings.

    The adapter never checks out or modifies the repository. It reads blobs from
    the observed commit, bounds the number/size of modules and re-probes HEAD
    before returning a complete FindingReport.
    """

    def __init__(self, adapter, authorize, *, max_files=MAX_FILES):
        if not callable(getattr(adapter, "analyze", None)) or not callable(authorize):
            raise ValueError("Trusted analyzer and authorization callback are required")
        if type(max_files) is not int or not 1 <= max_files <= MAX_FILES:
            raise ValueError("max_files must be bounded")
        self.adapter, self.authorize, self.max_files = adapter, authorize, max_files

    @staticmethod
    def _env():
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        env.update(
            GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1"
        )
        return env

    @classmethod
    def _run(cls, repository, *args):
        try:
            result = subprocess.run(
                [
                    "git",
                    "--no-pager",
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(repository),
                    *args,
                ],
                env=cls._env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CoreError(
                "GIT_ANALYZER_FAILED", "Git analyzer command failed"
            ) from exc
        if result.returncode != 0:
            raise CoreError("GIT_ANALYZER_FAILED", "Git analyzer command failed")
        return result.stdout

    @classmethod
    def _paths(cls, repository, commit, max_files):
        raw = cls._run(repository, "ls-tree", "-r", "--name-only", "-z", commit)
        paths = []
        for item in raw.split(b"\0"):
            if not item:
                continue
            try:
                value = item.decode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise CoreError(
                    "GIT_ANALYZER_PATH_INVALID", "Git path is not UTF-8"
                ) from exc
            if not _valid_path(value):
                raise CoreError("GIT_ANALYZER_PATH_INVALID", "Git path is unsafe")
            if Path(value).suffix.casefold() not in {".bsl", ".os"}:
                continue
            paths.append(value)
            if len(paths) > max_files:
                raise CoreError("GIT_ANALYZER_LIMIT", "Too many BSL modules in commit")
        return paths

    @classmethod
    def _blob(cls, repository, commit, path):
        raw = cls._run(repository, "cat-file", "blob", f"{commit}:{path}")
        if len(raw) > MAX_FILE:
            raise CoreError("GIT_ANALYZER_LIMIT", "BSL module exceeds analyzer limit")
        return raw

    @staticmethod
    def _findings(path, analysis):
        if not isinstance(analysis, BslAnalysis) or analysis.status != "completed":
            raise CoreError(
                "GIT_ANALYZER_INCOMPLETE",
                "BSL-LS did not return a complete analysis",
            )
        result = []
        seen = set()
        for diagnostic in analysis.diagnostics:
            start, end = diagnostic.start, diagnostic.end
            if (
                type(start.line) is not int
                or type(start.character) is not int
                or type(end.line) is not int
                or type(end.character) is not int
                or start.line < 0
                or start.character < 0
                or end.line < 0
                or end.character < 0
            ):
                raise CoreError(
                    "GIT_ANALYZER_INCOMPLETE",
                    "BSL-LS returned invalid diagnostic coordinates",
                )
            anchor = (
                f"{diagnostic.code}:{start.line}:{start.character}:"
                f"{end.line}:{end.character}"
            )
            if anchor in seen:
                raise CoreError(
                    "GIT_ANALYZER_DUPLICATE", "BSL-LS returned duplicate diagnostics"
                )
            seen.add(anchor)
            result.append(
                Finding(
                    rule="bsl/" + diagnostic.code,
                    path=path,
                    anchor=anchor,
                    message=diagnostic.message,
                    line=start.line + 1,
                )
            )
        return result

    def __call__(self, observation: GitObservation):
        if not isinstance(observation, GitObservation):
            raise CoreError("GIT_ANALYZER_CONTEXT", "Git observation is required")
        repository = Path(observation.repository).resolve()
        commit = observation.commit
        self.authorize()
        from rentgen_core.git_observer import observe_git

        if observe_git(repository) != observation:
            raise CoreError(
                "GIT_HEAD_CHANGED", "Observed Git HEAD is no longer current"
            )
        paths = self._paths(repository, commit, self.max_files)
        findings, used = [], 0
        for path in paths:
            self.authorize()
            raw = self._blob(repository, commit, path)
            used += len(raw)
            if used > MAX_TOTAL:
                raise CoreError(
                    "GIT_ANALYZER_LIMIT", "Git analyzer byte limit exceeded"
                )
            suffix = Path(path).suffix.lower()
            analysis = self.adapter.analyze(
                raw, suffix=suffix, authorize=self.authorize
            )
            if (
                not isinstance(analysis, BslAnalysis)
                or analysis.candidate_sha256 != hashlib.sha256(raw).hexdigest()
                or analysis.candidate_size_bytes != len(raw)
                or analysis.runtime_verified is not True
                or analysis.diagnostics_complete is not True
            ):
                raise CoreError(
                    "GIT_ANALYZER_INCOMPLETE",
                    "BSL-LS result is not bound to the committed blob",
                )
            findings.extend(self._findings(path, analysis))
        self.authorize()
        if observe_git(repository) != observation:
            raise CoreError("GIT_HEAD_CHANGED", "Git HEAD changed during BSL analysis")
        return FindingReport(
            observation=observation,
            profile_id=PROFILE_ID,
            scope_id=SCOPE_ID,
            complete=True,
            findings=tuple(findings),
        )
