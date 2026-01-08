"""Tests for CircuitBreaker class."""

import json
import time

from meshmon.retry import CircuitBreaker


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_creates_with_fresh_state(self, circuit_state_file):
        """Fresh circuit breaker has zero failures and no cooldown."""
        cb = CircuitBreaker(circuit_state_file)

        assert cb.consecutive_failures == 0
        assert cb.cooldown_until == 0
        assert cb.last_success == 0

    def test_loads_existing_state(self, closed_circuit):
        """Loads state from existing file."""
        cb = CircuitBreaker(closed_circuit)

        assert cb.consecutive_failures == 0
        assert cb.cooldown_until == 0
        assert cb.last_success > 0

    def test_loads_open_circuit_state(self, open_circuit):
        """Loads open circuit state correctly."""
        cb = CircuitBreaker(open_circuit)

        assert cb.consecutive_failures == 10
        assert cb.cooldown_until > time.time()
        assert cb.is_open() is True

    def test_handles_corrupted_file(self, corrupted_state_file):
        """Corrupted JSON file loads defaults without crashing."""
        cb = CircuitBreaker(corrupted_state_file)

        # Should use defaults
        assert cb.consecutive_failures == 0
        assert cb.cooldown_until == 0
        assert cb.last_success == 0

    def test_handles_partial_state(self, partial_state_file):
        """Missing keys in state file use defaults."""
        cb = CircuitBreaker(partial_state_file)

        assert cb.consecutive_failures == 5  # Present in file
        assert cb.cooldown_until == 0  # Default
        assert cb.last_success == 0  # Default

    def test_handles_nonexistent_file(self, circuit_state_file):
        """Nonexistent state file uses defaults."""
        assert not circuit_state_file.exists()

        cb = CircuitBreaker(circuit_state_file)

        assert cb.consecutive_failures == 0

    def test_stores_state_file_path(self, circuit_state_file):
        """Stores the state file path."""
        cb = CircuitBreaker(circuit_state_file)

        assert cb.state_file == circuit_state_file


class TestCircuitBreakerIsOpen:
    """Tests for is_open method."""

    def test_closed_circuit_returns_false(self, closed_circuit):
        """Closed circuit (no cooldown) returns False."""
        cb = CircuitBreaker(closed_circuit)

        assert cb.is_open() is False

    def test_open_circuit_returns_true(self, open_circuit):
        """Open circuit (in cooldown) returns True."""
        cb = CircuitBreaker(open_circuit)

        assert cb.is_open() is True

    def test_expired_cooldown_returns_false(self, expired_cooldown_circuit):
        """Expired cooldown returns False (circuit closes)."""
        cb = CircuitBreaker(expired_cooldown_circuit)

        assert cb.is_open() is False

    def test_cooldown_expiry(self, circuit_state_file):
        """Circuit closes when cooldown expires."""
        # Set cooldown to 0.1 seconds from now
        state = {
            "consecutive_failures": 10,
            "cooldown_until": time.time() + 0.1,
            "last_success": 0,
        }
        circuit_state_file.write_text(json.dumps(state))

        cb = CircuitBreaker(circuit_state_file)
        assert cb.is_open() is True

        time.sleep(0.15)
        assert cb.is_open() is False


class TestCooldownRemaining:
    """Tests for cooldown_remaining method."""

    def test_returns_zero_when_closed(self, closed_circuit):
        """Returns 0 when circuit is closed."""
        cb = CircuitBreaker(closed_circuit)

        assert cb.cooldown_remaining() == 0

    def test_returns_seconds_when_open(self, circuit_state_file):
        """Returns remaining seconds when in cooldown."""
        state = {
            "consecutive_failures": 10,
            "cooldown_until": time.time() + 100,
            "last_success": 0,
        }
        circuit_state_file.write_text(json.dumps(state))

        cb = CircuitBreaker(circuit_state_file)
        remaining = cb.cooldown_remaining()

        assert 98 <= remaining <= 100

    def test_returns_zero_when_expired(self, expired_cooldown_circuit):
        """Returns 0 when cooldown has expired."""
        cb = CircuitBreaker(expired_cooldown_circuit)

        assert cb.cooldown_remaining() == 0

    def test_returns_integer(self, open_circuit):
        """Returns an integer, not float."""
        cb = CircuitBreaker(open_circuit)

        assert isinstance(cb.cooldown_remaining(), int)


class TestRecordSuccess:
    """Tests for record_success method."""

    def test_resets_failure_count(self, circuit_state_file):
        """Success resets consecutive failure count to 0."""
        state = {
            "consecutive_failures": 5,
            "cooldown_until": 0,
            "last_success": 0,
        }
        circuit_state_file.write_text(json.dumps(state))

        cb = CircuitBreaker(circuit_state_file)
        cb.record_success()

        assert cb.consecutive_failures == 0

    def test_updates_last_success(self, circuit_state_file):
        """Success updates last_success timestamp."""
        cb = CircuitBreaker(circuit_state_file)
        before = time.time()
        cb.record_success()
        after = time.time()

        assert before <= cb.last_success <= after

    def test_persists_to_file(self, circuit_state_file):
        """Success state is persisted to file."""
        cb = CircuitBreaker(circuit_state_file)
        cb.consecutive_failures = 5
        cb.record_success()

        # Read file directly
        data = json.loads(circuit_state_file.read_text())
        assert data["consecutive_failures"] == 0
        assert data["last_success"] > 0

    def test_creates_parent_dirs(self, tmp_path):
        """Creates parent directories if they don't exist."""
        nested_path = tmp_path / "deep" / "nested" / "circuit.json"
        cb = CircuitBreaker(nested_path)
        cb.record_success()

        assert nested_path.exists()


class TestRecordFailure:
    """Tests for record_failure method."""

    def test_increments_failure_count(self, circuit_state_file):
        """Failure increments consecutive failure count."""
        cb = CircuitBreaker(circuit_state_file)
        cb.record_failure(max_failures=10, cooldown_s=3600)

        assert cb.consecutive_failures == 1

    def test_opens_circuit_at_threshold(self, circuit_state_file):
        """Circuit opens when failures reach threshold."""
        cb = CircuitBreaker(circuit_state_file)

        # Record failures up to threshold
        for _ in range(5):
            cb.record_failure(max_failures=5, cooldown_s=3600)

        assert cb.is_open() is True
        assert cb.cooldown_until > time.time()

    def test_does_not_open_before_threshold(self, circuit_state_file):
        """Circuit stays closed before reaching threshold."""
        cb = CircuitBreaker(circuit_state_file)

        for _ in range(4):
            cb.record_failure(max_failures=5, cooldown_s=3600)

        assert cb.is_open() is False

    def test_cooldown_duration(self, circuit_state_file):
        """Cooldown is set to specified duration."""
        cb = CircuitBreaker(circuit_state_file)

        before = time.time()
        for _ in range(5):
            cb.record_failure(max_failures=5, cooldown_s=100)
        after = time.time()

        # Cooldown should be ~100 seconds from now
        assert cb.cooldown_until >= before + 100
        assert cb.cooldown_until <= after + 100

    def test_persists_to_file(self, circuit_state_file):
        """Failure state is persisted to file."""
        cb = CircuitBreaker(circuit_state_file)
        cb.record_failure(max_failures=10, cooldown_s=3600)

        data = json.loads(circuit_state_file.read_text())
        assert data["consecutive_failures"] == 1


class TestToDict:
    """Tests for to_dict method."""

    def test_includes_all_fields(self, closed_circuit):
        """Dict includes all state fields."""
        cb = CircuitBreaker(closed_circuit)
        d = cb.to_dict()

        assert "consecutive_failures" in d
        assert "cooldown_until" in d
        assert "last_success" in d
        assert "is_open" in d
        assert "cooldown_remaining_s" in d

    def test_is_open_reflects_state(self, open_circuit):
        """is_open in dict reflects actual circuit state."""
        cb = CircuitBreaker(open_circuit)
        d = cb.to_dict()

        assert d["is_open"] is True

    def test_cooldown_remaining_reflects_state(self, open_circuit):
        """cooldown_remaining_s reflects actual remaining time."""
        cb = CircuitBreaker(open_circuit)
        d = cb.to_dict()

        assert d["cooldown_remaining_s"] > 0

    def test_closed_circuit_dict(self, closed_circuit):
        """Closed circuit has expected dict values."""
        cb = CircuitBreaker(closed_circuit)
        d = cb.to_dict()

        assert d["consecutive_failures"] == 0
        assert d["is_open"] is False
        assert d["cooldown_remaining_s"] == 0


class TestStatePersistence:
    """Tests for state persistence across instances."""

    def test_state_survives_reload(self, circuit_state_file):
        """State persists across CircuitBreaker instances."""
        cb1 = CircuitBreaker(circuit_state_file)
        cb1.record_failure(max_failures=10, cooldown_s=3600)
        cb1.record_failure(max_failures=10, cooldown_s=3600)
        cb1.record_failure(max_failures=10, cooldown_s=3600)

        # Create new instance
        cb2 = CircuitBreaker(circuit_state_file)

        assert cb2.consecutive_failures == 3

    def test_success_resets_across_reload(self, circuit_state_file):
        """Success reset persists across instances."""
        cb1 = CircuitBreaker(circuit_state_file)
        for _ in range(5):
            cb1.record_failure(max_failures=10, cooldown_s=3600)

        cb1.record_success()

        cb2 = CircuitBreaker(circuit_state_file)
        assert cb2.consecutive_failures == 0

    def test_open_state_survives_reload(self, circuit_state_file):
        """Open circuit state persists across instances."""
        cb1 = CircuitBreaker(circuit_state_file)
        for _ in range(10):
            cb1.record_failure(max_failures=10, cooldown_s=3600)

        assert cb1.is_open() is True

        cb2 = CircuitBreaker(circuit_state_file)
        assert cb2.is_open() is True
        assert cb2.consecutive_failures == 10
