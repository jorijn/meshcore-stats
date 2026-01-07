"""Tests for get_repeater_circuit_breaker function."""

import pytest
from pathlib import Path

from meshmon.retry import get_repeater_circuit_breaker, CircuitBreaker


class TestGetRepeaterCircuitBreaker:
    """Tests for get_repeater_circuit_breaker function."""

    def test_returns_circuit_breaker(self, configured_env):
        """Returns a CircuitBreaker instance."""
        cb = get_repeater_circuit_breaker()

        assert isinstance(cb, CircuitBreaker)

    def test_uses_state_dir(self, configured_env):
        """Uses state_dir from config."""
        cb = get_repeater_circuit_breaker()

        expected_path = configured_env["state_dir"] / "repeater_circuit.json"
        assert cb.state_file == expected_path

    def test_state_file_name(self, configured_env):
        """State file is named repeater_circuit.json."""
        cb = get_repeater_circuit_breaker()

        assert cb.state_file.name == "repeater_circuit.json"

    def test_each_call_creates_new_instance(self, configured_env):
        """Each call creates a new CircuitBreaker instance."""
        cb1 = get_repeater_circuit_breaker()
        cb2 = get_repeater_circuit_breaker()

        assert cb1 is not cb2

    def test_instances_share_state_file(self, configured_env):
        """Multiple instances share the same state file."""
        cb1 = get_repeater_circuit_breaker()
        cb2 = get_repeater_circuit_breaker()

        assert cb1.state_file == cb2.state_file

    def test_state_persists_across_instances(self, configured_env):
        """State changes persist across instances."""
        cb1 = get_repeater_circuit_breaker()
        cb1.record_failure(max_failures=10, cooldown_s=3600)
        cb1.record_failure(max_failures=10, cooldown_s=3600)

        cb2 = get_repeater_circuit_breaker()

        assert cb2.consecutive_failures == 2

    def test_creates_state_file_on_write(self, configured_env):
        """State file is created when recording success/failure."""
        state_dir = configured_env["state_dir"]
        state_file = state_dir / "repeater_circuit.json"

        assert not state_file.exists()

        cb = get_repeater_circuit_breaker()
        cb.record_success()

        assert state_file.exists()
