"""
Unit tests for LLMGateway resilience
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.llm_gateway import LLMGateway
from src.services.llm_provider_manager import ProviderConfig


class TestLLMGatewayResilience:
    """Test LLMGateway resilience features (timeouts, circuit breakers)"""

    @pytest.fixture
    def gateway(self):
        # Mock dependencies
        mock_manager = Mock()
        mock_manager.has_configuration.return_value = True
        mock_manager.get_active_provider.return_value = ProviderConfig(
            name="test-provider", enabled=True
        )
        mock_manager.get_fallback_chain.return_value = None

        return LLMGateway(
            manager=mock_manager,
            enable_cache=False,
            enable_health_monitoring=False,
            enable_circuit_breaker=True,
        )

    @pytest.mark.asyncio
    async def test_timeout_handling(self, gateway):
        """Test that provider calls timeout correctly"""

        # Mock a client that sleeps longer than timeout
        mock_client = AsyncMock()

        async def sleepy_generate(*args, **kwargs):
            await asyncio.sleep(0.2)
            return {"text": "too late"}

        mock_client.generate = sleepy_generate
        gateway.get_client = Mock(return_value=mock_client)

        # Build a provider chain manually or rely on manager
        # Here we just test the internal timeout wrapper logic indirectly via generate

        # Set a very short timeout via kwargs
        response = await gateway.generate("test prompt", timeout=0.1)

        # Expect fallback/placeholder response due to timeout
        # The gateway catches exceptions and returns offline fallback or placeholder
        assert response.metadata.get("offline") is True or "error" in response.metadata

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self, gateway):
        """Test circuit breaker prevents calls after failures"""
        # Manually trip the breaker
        breaker = gateway.circuit_breakers["test-provider"]
        breaker.state._failure_count = 10  # Exceed threshold
        breaker.state._state = "OPEN"
        breaker.state._last_failure_time = asyncio.get_event_loop().time()

        mock_client = AsyncMock()
        gateway.get_client = Mock(return_value=mock_client)

        # Call generate
        await gateway.generate("test")

        # Client should NOT be called
        mock_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_chain(self, gateway):
        """Test fallback to next provider on failure"""

        # Setup manager to return primary and secondary
        p1 = ProviderConfig(name="primary", enabled=True)
        p2 = ProviderConfig(name="secondary", enabled=True)

        gateway.manager.get_active_provider.return_value = p1
        gateway.manager.get_fallback_chain.return_value = {
            "primary": "primary",
            "chain": ["secondary"],
        }
        gateway.manager.get_provider.side_effect = lambda name: (
            p1 if name == "primary" else p2
        )

        # Setup clients
        mock_client_fail = AsyncMock()
        mock_client_fail.generate.side_effect = Exception("Connection Error")

        mock_client_success = AsyncMock()
        mock_client_success.generate.return_value = {"text": "Success", "usage": {}}

        gateway.get_client = Mock(
            side_effect=lambda name: (
                mock_client_fail if name == "primary" else mock_client_success
            )
        )

        # Init breakers for new providers
        from src.resilience.error_recovery import CircuitBreaker

        gateway.circuit_breakers["primary"] = CircuitBreaker()
        gateway.circuit_breakers["secondary"] = CircuitBreaker()

        response = await gateway.generate("test")

        assert response.provider == "secondary"
        assert response.response == "Success"
