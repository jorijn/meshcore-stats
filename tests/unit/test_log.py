"""Tests for logging utilities."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from meshmon import log


class TestTimestamp:
    """Test the _ts() timestamp function."""

    def test_returns_string(self):
        """_ts() should return a string."""
        result = log._ts()
        assert isinstance(result, str)

    def test_format_is_correct(self):
        """_ts() should return timestamp in expected format."""
        result = log._ts()
        # Format: YYYY-MM-DD HH:MM:SS
        try:
            datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pytest.fail(f"Timestamp '{result}' doesn't match expected format")

    @patch("meshmon.log.datetime")
    def test_uses_current_time(self, mock_datetime):
        """_ts() should use current time."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2024-01-15 10:30:45"
        mock_datetime.now.return_value = mock_now

        result = log._ts()

        mock_datetime.now.assert_called_once()
        mock_now.strftime.assert_called_once_with("%Y-%m-%d %H:%M:%S")
        assert result == "2024-01-15 10:30:45"


@pytest.fixture
def fixed_ts(monkeypatch):
    """Freeze log timestamp for deterministic output assertions."""
    timestamp = "2024-01-15 10:30:45"
    monkeypatch.setattr(log, "_ts", lambda: timestamp)
    return timestamp


class TestInfoLog:
    """Test the info() function."""

    def test_prints_to_stdout(self, capsys, fixed_ts):
        """info() should print to stdout."""
        log.info("test message")
        captured = capsys.readouterr()
        assert captured.out == f"[{fixed_ts}] test message\n"
        assert captured.err == ""

    def test_includes_timestamp(self, capsys, fixed_ts):
        """info() output should include timestamp."""
        log.info("test")
        captured = capsys.readouterr()
        # Should have format: [YYYY-MM-DD HH:MM:SS] message
        assert captured.out.startswith(f"[{fixed_ts}]")
        assert captured.out.endswith("test\n")

    def test_message_appears_after_timestamp(self, capsys, fixed_ts):
        """Message should appear after the timestamp."""
        log.info("unique_test_message")
        captured = capsys.readouterr()
        assert captured.out == f"[{fixed_ts}] unique_test_message\n"
        # Message should be after the closing bracket
        bracket_pos = captured.out.index("]")
        message_pos = captured.out.index("unique_test_message")
        assert message_pos > bracket_pos


class TestDebugLog:
    """Test the debug() function."""

    def test_no_output_when_debug_disabled(self, capsys, monkeypatch, fixed_ts):
        """debug() should not print when MESH_DEBUG is not set."""
        # Clean env should already have MESH_DEBUG unset
        import meshmon.env
        meshmon.env._config = None

        log.debug("debug message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_prints_when_debug_enabled(self, capsys, monkeypatch, fixed_ts):
        """debug() should print when MESH_DEBUG=1."""
        monkeypatch.setenv("MESH_DEBUG", "1")
        import meshmon.env
        meshmon.env._config = None

        log.debug("debug message")
        captured = capsys.readouterr()
        assert captured.out == f"[{fixed_ts}] DEBUG: debug message\n"

    def test_debug_prefix(self, capsys, monkeypatch, fixed_ts):
        """debug() output should include DEBUG: prefix."""
        monkeypatch.setenv("MESH_DEBUG", "1")
        import meshmon.env
        meshmon.env._config = None

        log.debug("test")
        captured = capsys.readouterr()
        assert captured.out == f"[{fixed_ts}] DEBUG: test\n"


class TestErrorLog:
    """Test the error() function."""

    def test_prints_to_stderr(self, capsys, fixed_ts):
        """error() should print to stderr."""
        log.error("error message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == f"[{fixed_ts}] ERROR: error message\n"

    def test_includes_error_prefix(self, capsys, fixed_ts):
        """error() output should include ERROR: prefix."""
        log.error("test error")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] ERROR: test error\n"

    def test_includes_timestamp(self, capsys, fixed_ts):
        """error() output should include timestamp."""
        log.error("test")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] ERROR: test\n"


class TestWarnLog:
    """Test the warn() function."""

    def test_prints_to_stderr(self, capsys, fixed_ts):
        """warn() should print to stderr."""
        log.warn("warning message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == f"[{fixed_ts}] WARN: warning message\n"

    def test_includes_warn_prefix(self, capsys, fixed_ts):
        """warn() output should include WARN: prefix."""
        log.warn("test warning")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] WARN: test warning\n"

    def test_includes_timestamp(self, capsys, fixed_ts):
        """warn() output should include timestamp."""
        log.warn("test")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] WARN: test\n"


class TestLogMessageFormatting:
    """Test message formatting across all log functions."""

    def test_info_handles_special_characters(self, capsys, fixed_ts):
        """info() should handle special characters in messages."""
        log.info("Message with 'quotes' and \"double quotes\"")
        captured = capsys.readouterr()
        assert captured.out == (
            f"[{fixed_ts}] Message with 'quotes' and \"double quotes\"\n"
        )

    def test_error_handles_newlines(self, capsys, fixed_ts):
        """error() should handle newlines in messages."""
        log.error("Line1\nLine2")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] ERROR: Line1\nLine2\n"

    def test_warn_handles_unicode(self, capsys, fixed_ts):
        """warn() should handle unicode characters."""
        log.warn("Warning: \u26a0 Alert!")
        captured = capsys.readouterr()
        assert captured.err == f"[{fixed_ts}] WARN: Warning: \u26a0 Alert!\n"
