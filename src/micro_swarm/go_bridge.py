"""Go Scanner Bridge — connects bsl-scan.exe with Python SwarmRouter.

Calls Go binary for fast parallel BSL scanning, then routes results
through Micro-Model Swarm for ML analysis.

Usage:
    from micro_swarm.go_bridge import GoBridge

    bridge = GoBridge()
    results = bridge.scan_and_review("/path/to/1c/project")
    for r in results:
        print(r.path, r.decision, r.response)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.micro_swarm.router import SwarmRouter


@dataclass
class BridgeResult:
    """Result of Go scan + Python SwarmRouter review."""

    path: str
    loc: int
    decision: str
    response: str | None
    confidence: float
    scores: dict[str, float]
    go_features: dict[str, float]


class GoBridge:
    """Bridge between Go bsl-scan and Python SwarmRouter.

    Scans BSL files with Go (fast, parallel), then routes through
    SwarmRouter for ML analysis and template responses.
    """

    def __init__(
        self,
        binary: str | None = None,
        router: SwarmRouter | None = None,
        workers: int = 0,
        min_loc: int = 0,
    ) -> None:
        self.binary = binary or self._find_binary()
        self.router = router or SwarmRouter.default()
        self.workers = workers
        self.min_loc = min_loc

    @staticmethod
    def _find_binary() -> str:
        """Find bsl-scan binary relative to project root."""
        candidates = [
            Path(__file__).parent.parent.parent / "go" / "bsl-scan.exe",
            Path(__file__).parent.parent.parent / "go" / "bsl-scan",
            Path("go") / "bsl-scan.exe",
            Path("go") / "bsl-scan",
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        msg = "bsl-scan binary not found. Run: cd go && go build -o bsl-scan.exe ./cmd/bsl-scan/"
        raise FileNotFoundError(msg)

    def scan(self, path: str) -> list[dict[str, Any]]:
        """Run Go scanner on path, return raw JSON results."""
        cmd = [self.binary, "-format", "json"]
        if self.workers > 0:
            cmd.extend(["-workers", str(self.workers)])
        if self.min_loc > 0:
            cmd.extend(["-min-loc", str(self.min_loc)])
        cmd.append(path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.returncode != 0:
            msg = f"bsl-scan failed: {result.stderr}"
            raise RuntimeError(msg)

        data = json.loads(result.stdout)
        return data.get("files", [])

    def scan_and_review(self, path: str) -> list[BridgeResult]:
        """Full pipeline: Go scan → SwarmRouter review."""
        files = self.scan(path)
        results = []

        for file_data in files:
            if file_data.get("error"):
                continue

            features = file_data.get("features", {})
            file_path = file_data.get("path", "")
            loc = file_data.get("loc", 0)

            # Route through SwarmRouter using pre-extracted features
            router_result = self.router.review_from_features(features)

            results.append(
                BridgeResult(
                    path=file_path,
                    loc=loc,
                    decision=router_result.decision.value,
                    response=router_result.response,
                    confidence=router_result.confidence,
                    scores=router_result.scores,
                    go_features=features,
                )
            )

        return results

    def scan_summary(self, path: str) -> dict[str, Any]:
        """Scan and return summary statistics."""
        results = self.scan_and_review(path)

        decisions = {"clean": 0, "template": 0, "llm_required": 0}
        for r in results:
            decisions[r.decision] = decisions.get(r.decision, 0) + 1

        total_loc = sum(r.loc for r in results)

        return {
            "total_files": len(results),
            "total_loc": total_loc,
            "decisions": decisions,
            "llm_savings_pct": round(
                (1 - decisions.get("llm_required", 0) /
                 max(len(results), 1)) * 100, 1
            ),
        }
