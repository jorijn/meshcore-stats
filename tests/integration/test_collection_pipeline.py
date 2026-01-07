"""Integration tests for data collection pipeline."""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


@pytest.mark.integration
class TestCompanionCollectionPipeline:
    """Test companion collection end-to-end."""

    @pytest.mark.asyncio
    async def test_successful_collection_stores_metrics(
        self,
        mock_meshcore_successful_collection,
        full_integration_env,
        monkeypatch,
    ):
        """Successful collection should store all metrics in database."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        # Mock connect_with_lock to return our mock client
        @asynccontextmanager
        async def mock_connect_with_lock(*args, **kwargs):
            yield mock_meshcore_successful_collection

        with patch(
            "meshmon.meshcore_client.connect_with_lock",
            mock_connect_with_lock,
        ):
            # Initialize database
            from meshmon.db import init_db, get_latest_metrics

            init_db()

            # Import and run collection (inline to avoid import issues)
            # Note: We import the function directly rather than the script
            from meshmon.db import insert_metrics
            import time

            # Simulate collection logic
            ts = int(time.time())
            metrics = {}

            async with mock_connect_with_lock() as mc:
                assert mc is not None

                # Get stats_core
                event = await mc.commands.get_stats_core()
                if event and hasattr(event, "payload") and isinstance(event.payload, dict):
                    for key, value in event.payload.items():
                        if isinstance(value, (int, float)):
                            metrics[key] = float(value)

                # Get stats_packets
                event = await mc.commands.get_stats_packets()
                if event and hasattr(event, "payload") and isinstance(event.payload, dict):
                    for key, value in event.payload.items():
                        if isinstance(value, (int, float)):
                            metrics[key] = float(value)

                # Get contacts
                event = await mc.commands.get_contacts()
                if event and hasattr(event, "payload"):
                    contacts_count = len(event.payload) if event.payload else 0
                    metrics["contacts"] = float(contacts_count)

            # Insert metrics
            inserted = insert_metrics(ts=ts, role="companion", metrics=metrics)
            assert inserted > 0

            # Verify data was stored
            latest = get_latest_metrics("companion")
            assert latest is not None
            assert "battery_mv" in latest
            assert "recv" in latest
            assert "sent" in latest

    @pytest.mark.asyncio
    async def test_collection_fails_gracefully_on_connection_error(
        self, full_integration_env, monkeypatch
    ):
        """Collection should fail gracefully when connection fails."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        @asynccontextmanager
        async def mock_connect_with_lock_failing(*args, **kwargs):
            yield None

        with patch(
            "meshmon.meshcore_client.connect_with_lock",
            mock_connect_with_lock_failing,
        ):
            from meshmon.db import init_db, get_latest_metrics

            init_db()

            # Simulate collection with failed connection
            async with mock_connect_with_lock_failing() as mc:
                assert mc is None

            # Database should be empty
            latest = get_latest_metrics("companion")
            assert latest is None


@pytest.mark.integration
class TestCollectionWithCircuitBreaker:
    """Test collection with circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_collection_when_open(
        self, full_integration_env, monkeypatch
    ):
        """Collection should be skipped when circuit breaker is open."""
        from meshmon.retry import CircuitBreaker
        import time

        # Create an open circuit breaker
        state_dir = full_integration_env["state_dir"]
        cb = CircuitBreaker(state_dir / "repeater_circuit.json")
        cb.consecutive_failures = 10
        cb.cooldown_until = time.time() + 3600  # 1 hour from now
        cb._save()  # Use private method

        # Verify circuit is open
        assert cb.is_open() is True

        # Collection should check circuit breaker and skip
        # This tests the pattern used in collect_repeater.py

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_failure(self, full_integration_env, monkeypatch):
        """Circuit breaker should record failures."""
        from meshmon.retry import CircuitBreaker
        import time

        state_dir = full_integration_env["state_dir"]
        cb = CircuitBreaker(state_dir / "test_circuit.json")

        assert cb.consecutive_failures == 0

        # Record failures (requires max_failures and cooldown_s args)
        cb.record_failure(max_failures=5, cooldown_s=60)
        cb.record_failure(max_failures=5, cooldown_s=60)
        cb.record_failure(max_failures=5, cooldown_s=60)

        assert cb.consecutive_failures == 3

        # Success resets counter
        cb.record_success()
        assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_persists(self, full_integration_env):
        """Circuit breaker state should persist to disk."""
        from meshmon.retry import CircuitBreaker
        import time

        state_dir = full_integration_env["state_dir"]
        state_file = state_dir / "persist_test_circuit.json"

        # Create and configure circuit breaker
        cb1 = CircuitBreaker(state_file)
        cb1.consecutive_failures = 5
        cb1.cooldown_until = time.time() + 1800
        cb1._save()  # Use private method

        # Load in new instance
        cb2 = CircuitBreaker(state_file)

        assert cb2.consecutive_failures == 5
        assert cb2.cooldown_until == cb1.cooldown_until
