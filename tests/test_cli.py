"""Tests for CLI (isolated from ~/.ai-guider)."""

from typer.testing import CliRunner

from guider.cli import app

runner = CliRunner()


class TestCLI:
    def test_status_command(self, isolated_home) -> None:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "AI Guider Status" in result.stdout

    def test_config_command(self, isolated_home) -> None:
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "balanced" in result.stdout

    def test_missions_command(self, isolated_home) -> None:
        result = runner.invoke(app, ["missions"])
        assert result.exit_code == 0

    def test_resume_no_mission(self, isolated_home) -> None:
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert "No active mission" in result.stdout

    def test_map_command(self, isolated_home, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
        result = runner.invoke(app, ["map", "--workspace", str(tmp_path), "--json"])
        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "app.py" in result.stdout
