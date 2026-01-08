"""
Smoke tests for all executable scripts.

These tests verify that scripts can be imported without errors,
ensuring all dependencies and syntax are correct.
"""

from pathlib import Path

import pytest

from tests.scripts.conftest import load_script_module

# Scripts directory
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"


class TestScriptImports:
    """Smoke tests - verify all scripts can be imported."""

    def test_collect_companion_imports(self):
        """collect_companion.py imports without error."""
        module = load_script_module("collect_companion.py")
        assert hasattr(module, "main")
        assert hasattr(module, "collect_companion")
        assert callable(module.main)

    def test_collect_repeater_imports(self):
        """collect_repeater.py imports without error."""
        module = load_script_module("collect_repeater.py")
        assert hasattr(module, "main")
        assert hasattr(module, "collect_repeater")
        assert hasattr(module, "find_repeater_contact")
        assert callable(module.main)

    def test_render_charts_imports(self):
        """render_charts.py imports without error."""
        module = load_script_module("render_charts.py")
        assert hasattr(module, "main")
        assert callable(module.main)

    def test_render_site_imports(self):
        """render_site.py imports without error."""
        module = load_script_module("render_site.py")
        assert hasattr(module, "main")
        assert callable(module.main)

    def test_render_reports_imports(self):
        """render_reports.py imports without error."""
        module = load_script_module("render_reports.py")
        assert hasattr(module, "main")
        assert hasattr(module, "safe_write")
        assert hasattr(module, "get_node_name")
        assert hasattr(module, "get_location")
        assert hasattr(module, "render_monthly_report")
        assert hasattr(module, "render_yearly_report")
        assert hasattr(module, "build_reports_index_data")
        assert callable(module.main)

    def test_generate_snapshots_imports(self):
        """generate_snapshots.py imports without error."""
        module = load_script_module("generate_snapshots.py")
        # This utility script uses direct function calls instead of main()
        assert hasattr(module, "generate_svg_snapshots")
        assert hasattr(module, "generate_txt_snapshots")
        assert callable(module.generate_svg_snapshots)


class TestScriptStructure:
    """Verify scripts follow expected patterns."""

    @pytest.mark.parametrize(
        "script_name",
        [
            "collect_companion.py",
            "collect_repeater.py",
            "render_charts.py",
            "render_site.py",
            "render_reports.py",
        ],
    )
    def test_script_has_main_guard(self, script_name: str):
        """Scripts have if __name__ == '__main__' guard."""
        script_path = SCRIPTS_DIR / script_name
        content = script_path.read_text()
        assert 'if __name__ == "__main__":' in content

    @pytest.mark.parametrize(
        "script_name",
        [
            "collect_companion.py",
            "collect_repeater.py",
            "render_charts.py",
            "render_site.py",
            "render_reports.py",
        ],
    )
    def test_script_has_docstring(self, script_name: str):
        """Scripts have module-level docstring."""
        script_path = SCRIPTS_DIR / script_name
        content = script_path.read_text()
        # Should start with shebang, then docstring
        lines = content.split("\n")
        assert lines[0].startswith("#!/")
        assert lines[1] == '"""'

    @pytest.mark.parametrize(
        "script_name",
        [
            "collect_companion.py",
            "collect_repeater.py",
            "render_charts.py",
            "render_site.py",
            "render_reports.py",
        ],
    )
    def test_script_calls_init_db(self, script_name: str):
        """Scripts initialize database before operations."""
        script_path = SCRIPTS_DIR / script_name
        content = script_path.read_text()
        assert "init_db()" in content
