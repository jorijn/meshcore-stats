"""Fixtures for retry and circuit breaker tests."""

import json

import pytest

BASE_TS = 1704067200


@pytest.fixture
def circuit_state_file(tmp_path):
    """Path for circuit breaker state file."""
    return tmp_path / "circuit.json"


@pytest.fixture
def closed_circuit(circuit_state_file):
    """Circuit breaker state file with closed circuit (no failures)."""
    state = {
        "consecutive_failures": 0,
        "cooldown_until": 0,
        "last_success": BASE_TS,
    }
    circuit_state_file.write_text(json.dumps(state))
    return circuit_state_file


@pytest.fixture
def open_circuit(circuit_state_file):
    """Circuit breaker state file with open circuit (in cooldown)."""
    state = {
        "consecutive_failures": 10,
        "cooldown_until": BASE_TS + 3600,  # 1 hour from BASE_TS
        "last_success": BASE_TS - 7200,  # 2 hours before BASE_TS
    }
    circuit_state_file.write_text(json.dumps(state))
    return circuit_state_file


@pytest.fixture
def expired_cooldown_circuit(circuit_state_file):
    """Circuit breaker state file with expired cooldown."""
    state = {
        "consecutive_failures": 10,
        "cooldown_until": BASE_TS - 100,  # Expired 100s before BASE_TS
        "last_success": BASE_TS - 7200,
    }
    circuit_state_file.write_text(json.dumps(state))
    return circuit_state_file


@pytest.fixture
def corrupted_state_file(circuit_state_file):
    """Circuit breaker state file with corrupted JSON."""
    circuit_state_file.write_text("not valid json {{{")
    return circuit_state_file


@pytest.fixture
def partial_state_file(circuit_state_file):
    """Circuit breaker state file with missing keys."""
    state = {
        "consecutive_failures": 5,
        # Missing cooldown_until and last_success
    }
    circuit_state_file.write_text(json.dumps(state))
    return circuit_state_file
