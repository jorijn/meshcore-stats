"""Script-specific test fixtures."""

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure scripts can import from src
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
SRC_DIR = Path(__file__).parent.parent.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Track dynamically loaded script modules for cleanup
_loaded_script_modules: set[str] = set()


def load_script_module(script_name: str):
    """Load a script as a module and track it for cleanup.

    Args:
        script_name: Name of script file (e.g., "collect_companion.py")

    Returns:
        Loaded module object
    """
    script_path = SCRIPTS_DIR / script_name
    module_name = script_name.replace(".py", "")

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None, f"Could not load spec for {script_path}"
    assert spec.loader is not None, f"No loader for {script_path}"

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    _loaded_script_modules.add(module_name)

    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cleanup_script_modules():
    """Clean up dynamically loaded script modules after each test.

    This prevents test pollution where module-level state persists
    between tests, potentially causing false positives or flaky tests.
    """
    # Clear tracking before test
    _loaded_script_modules.clear()

    yield

    # Clean up after test
    for module_name in _loaded_script_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]
    _loaded_script_modules.clear()


@pytest.fixture
def scripts_dir():
    """Path to the scripts directory."""
    return SCRIPTS_DIR


@contextmanager
def mock_async_context_manager(return_value=None):
    """Create a mock that works as an async context manager.

    Usage:
        with patch.object(module, "connect_with_lock") as mock_connect:
            mock_connect.return_value = mock_async_context_manager(mc)
            # or for None return:
            mock_connect.return_value = mock_async_context_manager(None)

    Args:
        return_value: Value to return from __aenter__

    Returns:
        A mock configured as an async context manager
    """
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=return_value)
    mock.__aexit__ = AsyncMock(return_value=None)
    yield mock


class AsyncContextManagerMock:
    """A class-based async context manager mock for more complex scenarios.

    Can be configured with enter/exit callbacks and exception handling.
    """

    def __init__(self, return_value=None, exit_exception=None):
        """Initialize the mock.

        Args:
            return_value: Value to return from __aenter__
            exit_exception: Exception to raise in __aexit__ (for testing cleanup)
        """
        self.return_value = return_value
        self.exit_exception = exit_exception
        self.entered = False
        self.exited = False
        self.exit_args = None

    async def __aenter__(self):
        self.entered = True
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        self.exit_args = (exc_type, exc_val, exc_tb)
        if self.exit_exception:
            raise self.exit_exception
        return None


@pytest.fixture
def async_context_manager_factory():
    """Factory fixture to create async context manager mocks.

    Usage:
        def test_something(async_context_manager_factory):
            mc = MagicMock()
            ctx_mock = async_context_manager_factory(mc)
            with patch.object(module, "connect_with_lock", return_value=ctx_mock):
                ...
    """

    def factory(return_value=None, exit_exception=None):
        return AsyncContextManagerMock(return_value, exit_exception)

    return factory


@pytest.fixture
def mock_repeater_contact():
    """Mock repeater contact for testing."""
    return {
        "adv_name": "TestRepeater",
        "public_key": "abc123def456",
        "last_seen": 1234567890,
    }


@pytest.fixture
def mock_repeater_status(sample_repeater_metrics):
    """Mock repeater status response."""
    return sample_repeater_metrics.copy()


@pytest.fixture
def mock_run_command_factory():
    """Factory to create mock run_command functions with configurable responses.

    Usage:
        def test_something(mock_run_command_factory):
            responses = {
                "send_appstart": (True, "SELF_INFO", {}, None),
                "get_stats_core": (True, "STATS_CORE", {"battery_mv": 3850}, None),
            }
            mock_run = mock_run_command_factory(responses)
            with patch.object(module, "run_command", side_effect=mock_run):
                ...
    """

    def factory(responses: dict, default_response=None):
        """Create a mock run_command function.

        Args:
            responses: Dict mapping command names to (ok, evt_type, payload, err) tuples
            default_response: Response for commands not in responses dict.
                             If None, returns (False, None, None, "Unknown command")
        """
        if default_response is None:
            default_response = (False, None, None, "Unknown command")

        async def mock_run_command(mc, coro, name):
            return responses.get(name, default_response)

        return mock_run_command

    return factory
