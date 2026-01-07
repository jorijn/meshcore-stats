"""Fixtures for configuration tests."""

import pytest
import os


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Create a temporary config file and set up paths.

    Returns a helper to write config content.
    """
    config_path = tmp_path / "meshcore.conf"

    # Helper function to write config content
    def write_config(content: str):
        config_path.write_text(content)
        return config_path

    return write_config


@pytest.fixture
def isolate_config_loading(monkeypatch):
    """Isolate config loading by clearing all mesh-related env vars.

    This fixture goes beyond clean_env by ensuring a completely
    clean slate for testing config file loading.
    """
    # Clear all env vars that might affect config
    env_prefixes = (
        "MESH_", "REPEATER_", "COMPANION_", "REMOTE_",
        "TELEMETRY_", "REPORT_", "RADIO_", "STATE_DIR", "OUT_DIR"
    )
    for key in list(os.environ.keys()):
        for prefix in env_prefixes:
            if key.startswith(prefix):
                monkeypatch.delenv(key, raising=False)
                break

    # Reset config singleton
    import meshmon.env
    meshmon.env._config = None

    yield

    # Reset again after test
    meshmon.env._config = None
