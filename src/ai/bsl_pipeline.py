"""
BSL Analysis Pipeline — end-to-end code review orchestration.

Flow: Scan BSL files -> SwarmRouter triage -> Template/LLM response -> Feedback recording

This is a plain Python pipeline. No framework needed — the conditional routing
is a simple if/elif/else on SwarmRouter's decision.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.micro_swarm.router import RouterDecision, SwarmRouter

logger = logging.getLogger(__name__)


# ── LLM provider protocol (optional adapter) ─────────────────────


class LLMProvider(Protocol):
    """Protocol for LLM providers — any callable that reviews BSL code."""

    def review(self, code: str, scores: dict[str, float]) -> str:
        ...


# ── Result model ──────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Result of BSL pipeline analysis for a single file."""

    file_path: str
    decision: str  # clean / template / llm_required
    response: str | None = None
    scores: dict[str, float] = field(default_factory=dict)
    llm_model: str | None = None


# ── Pipeline ──────────────────────────────────────────────────────


class BSLPipeline:
    """End-to-end BSL code review pipeline.

    Scans BSL files, routes through SwarmRouter, generates responses.

    Args:
        project_path: path to 1C project directory with .bsl files
        llm_provider: optional LLM provider for complex cases
    """

    def __init__(
        self,
        project_path: str,
        llm_provider: Any | None = None,
    ) -> None:
        self.project_path = Path(project_path)
        self.llm_provider = llm_provider
        self.router = SwarmRouter.default()
        self._go_bridge: Any | None = None
        self._init_go_bridge()

    def _init_go_bridge(self) -> None:
        """Try to initialise GoBridge; fall back silently if unavailable."""
        try:
            from src.micro_swarm.go_bridge import GoBridge

            self._go_bridge = GoBridge(router=self.router)
            logger.info("GoBridge initialised — using Go scanner")
        except (FileNotFoundError, ImportError) as exc:
            logger.info("GoBridge unavailable (%s), using Python extractors", exc)
            self._go_bridge = None

    # ── file discovery ────────────────────────────────────────────

    def _find_bsl_files(self) -> list[Path]:
        """Recursively find all .bsl files under project_path."""
        files = sorted(self.project_path.rglob("*.bsl"))
        logger.info("Found %d BSL files in %s", len(files), self.project_path)
        return files

    # ── single-file analysis ──────────────────────────────────────

    def _analyse_file(self, path: Path) -> PipelineResult:
        """Analyse one BSL file through the router."""
        code = path.read_text(encoding="utf-8-sig", errors="replace")
        result = self.router.review(code)

        response = result.response
        llm_model: str | None = None

        if result.decision == RouterDecision.LLM_REQUIRED:
            if self.llm_provider is not None:
                logger.info("LLM review requested for %s", path)
                try:
                    response = self.llm_provider.review(code, result.scores)
                    llm_model = getattr(self.llm_provider, "model_name", "unknown")
                except Exception:
                    logger.exception("LLM review failed for %s", path)
            else:
                logger.debug("LLM required for %s but no provider configured", path)

            # Record feedback for self-training
            self.router.record_feedback(
                code=code,
                swarm_scores=result.scores,
                llm_verdict=response or "pending",
            )

        return PipelineResult(
            file_path=str(path),
            decision=result.decision.value,
            response=response,
            scores=result.scores,
            llm_model=llm_model,
        )

    # ── Go bridge path (scan whole project at once) ───────────────

    def _run_with_go(self) -> list[PipelineResult]:
        """Run pipeline using Go scanner for feature extraction."""
        from src.micro_swarm.go_bridge import BridgeResult

        assert self._go_bridge is not None
        bridge_results: list[BridgeResult] = self._go_bridge.scan_and_review(
            str(self.project_path),
        )

        results: list[PipelineResult] = []
        for br in bridge_results:
            llm_model: str | None = None
            response = br.response

            if br.decision == "llm_required" and self.llm_provider is not None:
                try:
                    code = Path(br.path).read_text(
                        encoding="utf-8-sig", errors="replace"
                    )
                    response = self.llm_provider.review(code, br.scores)
                    llm_model = getattr(self.llm_provider, "model_name", "unknown")
                except Exception:
                    logger.exception("LLM review failed for %s", br.path)

            results.append(
                PipelineResult(
                    file_path=br.path,
                    decision=br.decision,
                    response=response,
                    scores=br.scores,
                    llm_model=llm_model,
                )
            )
        return results

    # ── public API ────────────────────────────────────────────────

    def run(self) -> list[PipelineResult]:
        """Execute the pipeline synchronously.

        Returns:
            List of PipelineResult, one per BSL file.
        """
        # Fast path: Go scanner handles everything in one subprocess call
        if self._go_bridge is not None:
            try:
                return self._run_with_go()
            except (RuntimeError, OSError) as exc:
                logger.warning("Go scanner failed (%s), falling back to Python", exc)

        # Slow path: Python extractors, file-by-file
        bsl_files = self._find_bsl_files()
        results = [self._analyse_file(f) for f in bsl_files]

        clean = sum(1 for r in results if r.decision == "clean")
        tpl = sum(1 for r in results if r.decision == "template")
        llm = sum(1 for r in results if r.decision == "llm_required")
        logger.info(
            "Pipeline complete: %d files (clean=%d, template=%d, llm=%d)",
            len(results),
            clean,
            tpl,
            llm,
        )
        return results

    async def arun(self) -> list[PipelineResult]:
        """Async version — runs sync pipeline in executor for now.

        Future: will use async LLM calls for LLM_REQUIRED files.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)


# ── Convenience function ──────────────────────────────────────────


def run_pipeline(project_path: str) -> list[PipelineResult]:
    """One-liner to run the BSL analysis pipeline.

    Args:
        project_path: path to 1C project with .bsl files

    Returns:
        List of PipelineResult for each analysed file.
    """
    pipeline = BSLPipeline(project_path)
    return pipeline.run()


# ── CLI entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    path = sys.argv[1] if len(sys.argv) > 1 else "."
    results = run_pipeline(path)

    for r in results:
        icon = {
            "clean": "\u2705",
            "template": "\U0001f536",
            "llm_required": "\U0001f534",
        }.get(r.decision, "?")
        print(f"  {icon} {r.file_path} [{r.decision}]")
        if r.response:
            for line in r.response.splitlines():
                print(f"      {line}")

    total = len(results)
    llm_needed = sum(1 for r in results if r.decision == "llm_required")
    savings = round((1 - llm_needed / max(total, 1)) * 100, 1)
    print(f"\n  {total} files | LLM savings: {savings}%")
