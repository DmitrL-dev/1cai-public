import pytest

from src.integrations.cicd_client import CICD_EVIDENCE_CONTRACT, CICDClient, CIPlatform


@pytest.mark.asyncio
async def test_github_actions_test_results_require_artifact_evidence():
    client = CICDClient(CIPlatform.GITHUB, api_token="token")

    result = await client.get_test_results("owner/repo", "123")

    assert result["status"] == "needs_evidence"
    assert result["mode"] == CICD_EVIDENCE_CONTRACT
    assert result["coverage"] == "github_actions_run_metadata_only"
    assert result["total"] is None
    assert result["measured"] is False
    assert "JUnit XML artifact" in result["required_evidence"]
    assert "zero total" in result["caveats"][1].lower()
