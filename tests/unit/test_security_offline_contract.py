import pytest

from src.ai.agents.security_agent import SecurityAgent
from src.ai.llm import AdaptiveLLMSelector, TaskType
from src.integrations.cve_database_client import CVEDatabaseClient


@pytest.mark.asyncio
async def test_llm_module_exposes_honest_offline_fallback():
    selector = AdaptiveLLMSelector()

    result = await selector.generate(
        task_type=TaskType.SECURITY_ANALYSIS,
        prompt="Check security",
        context={"source": "unit"},
    )

    assert selector.available is False
    assert result["mode"] == "offline_fallback"
    assert result["coverage"] == "no_llm_provider"
    assert "llm_offline_fallback" in result["response"]


@pytest.mark.asyncio
async def test_security_dependency_audit_does_not_claim_safe_without_cve_source():
    agent = SecurityAgent()

    result = await agent.process(
        {
            "scan_type": "dependency_audit",
            "dependencies": [{"name": "demo-lib", "version": "1.0.0"}],
        }
    )

    assert result["mode"] == "offline_dependency_audit"
    assert result["coverage"] == "no_cve_database"
    assert result["vulnerability_measured"] is False
    assert result["vulnerable_count"] == 0
    assert result["caveats"]


@pytest.mark.asyncio
async def test_security_sast_and_dast_are_bounded_when_tools_are_not_configured():
    agent = SecurityAgent()

    sast = await agent.run_sast_scan('password = "secret"', language="python")
    dast = await agent.run_dast_scan("https://example.invalid")
    llm = await agent.analyze_with_llm("password = 'secret'")

    assert sast["status"] == "success"
    assert sast["mode"] == "local_regex_security_scan"
    assert sast["coverage"] == "regex_patterns_only"
    assert sast["total_count"] >= 1
    assert dast["status"] == "needs_configuration"
    assert dast["findings_measured"] is False
    assert llm["status"] == "llm_offline_fallback"
    assert llm["coverage"] == "no_llm_provider"


@pytest.mark.asyncio
async def test_cve_client_has_no_fake_osv_source_in_baseline():
    client = CVEDatabaseClient()

    cves = await client.check_vulnerability("demo-lib", "1.0.0")

    assert client.osv_client is None
    assert cves == []
