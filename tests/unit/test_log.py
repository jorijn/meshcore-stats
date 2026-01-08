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


class TestInfoLog:
    """Test the info() function."""

    def test_prints_to_stdout(self, capsys):
        """info() should print to stdout."""
        log.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out
        assert captured.err == ""

    def test_includes_timestamp(self, capsys):
        """info() output should include timestamp."""
        log.info("test")
        captured = capsys.readouterr()
        # Should have format: [YYYY-MM-DD HH:MM:SS] message
        assert captured.out.startswith("[")
        assert "]" in captured.out

    def test_message_appears_after_timestamp(self, capsys):
        """Message should appear after the timestamp."""
        log.info("unique_test_message")
        captured = capsys.readouterr()
        assert "unique_test_message" in captured.out
        # Message should be after the closing bracket
        bracket_pos = captured.out.index("]")
        message_pos = captured.out.index("unique_test_message")
        assert message_pos > bracket_pos


class TestDebugLog:
    """Test the debug() function."""

    def test_no_output_when_debug_disabled(self, capsys, monkeypatch):
        """debug() should not print when MESH_DEBUG is not set."""
        # Clean env should already have MESH_DEBUG unset
        import meshmon.env
        meshmon.env._config = None

        log.debug("debug message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_prints_when_debug_enabled(self, capsys, monkeypatch):
        """debug() should print when MESH_DEBUG=1."""
        monkeypatch.setenv("MESH_DEBUG", "1")
        import meshmon.env
        meshmon.env._config = None

        log.debug("debug message")
        captured = capsys.readouterr()
        assert "debug message" in captured.out
        assert "DEBUG:" in captured.out

    def test_debug_prefix(self, capsys, monkeypatch):
        """debug() output should include DEBUG: prefix."""
        monkeypatch.setenv("MESH_DEBUG", "1")
        import meshmon.env
        meshmon.env._config = None

        log.debug("test")
        captured = capsys.readouterr()
        assert "DEBUG:" in captured.out


class TestErrorLog:
    """Test the error() function."""

    def test_prints_to_stderr(self, capsys):
        """error() should print to stderr."""
        log.error("error message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "error message" in captured.err

    def test_includes_error_prefix(self, capsys):
        """error() output should include ERROR: prefix."""
        log.error("test error")
        captured = capsys.readouterr()
        assert "ERROR:" in captured.err

    def test_includes_timestamp(self, capsys):
        """error() output should include timestamp."""
        log.error("test")
        captured = capsys.readouterr()
        assert captured.err.startswith("[")
        assert "]" in captured.err


class TestWarnLog:
    """Test the warn() function."""

    def test_prints_to_stderr(self, capsys):
        """warn() should print to stderr."""
        log.warn("warning message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "warning message" in captured.err

    def test_includes_warn_prefix(self, capsys):
        """warn() output should include WARN: prefix."""
        log.warn("test warning")
        captured = capsys.readouterr()
        assert "WARN:" in captured.err

    def test_includes_timestamp(self, capsys):
        """warn() output should include timestamp."""
        log.warn("test")
        captured = capsys.readouterr()
        assert captured.err.startswith("[")
        assert "]" in captured.err


class TestLogMessageFormatting:
    """Test message formatting across all log functions."""

    def test_info_handles_special_characters(self, capsys):
        """info() should handle special characters in messages."""
        log.info("Message with 'quotes' and \"double quotes\"")
        captured = capsys.readouterr()
        assert "'quotes'" in captured.out
        assert '"double quotes"' in captured.out

    def test_error_handles_newlines(self, capsys):
        """error() should handle newlines in messages."""
        log.error("Line1\nLine2")
        captured = capsys.readouterr()
        assert "Line1\nLine2" in captured.err

    def test_warn_handles_unicode(self, capsys):
        """warn() should handle unicode characters."""
        log.warn("Warning: \u26a0 Alert!")
        captured = capsys.readouterr()
        assert "\u26a0" in captured.err
