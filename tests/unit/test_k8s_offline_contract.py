import pytest

from src.integrations.k8s_client import KubernetesClient


@pytest.mark.asyncio
async def test_kubernetes_client_returns_offline_contract_without_adapter():
    client = KubernetesClient(config_file="missing-kubeconfig")

    deploy = await client.deploy_app("rentgen", "rentgen:local", replicas=2)
    scale = await client.scale_deployment("rentgen", 3)
    status = await client.get_deployment_status("rentgen")
    logs = await client.get_pod_logs("rentgen-0")

    for result in (deploy, scale, status, logs):
        assert result["mode"] == "offline_kubernetes_contract"
        assert result["status"] == "needs_configuration"
        assert result["applied"] is False
        assert result["configured"] is False
        assert result["required_evidence"]
        assert "pending_implementation" not in str(result)
