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

    def test_help_command_guide(self, isolated_home) -> None:
        result = runner.invoke(app, ["help"])
        assert result.exit_code == 0
        assert "command guide" in result.stdout.lower() or "AI Guider" in result.stdout
        assert "init" in result.stdout
        assert "--all-clients" in result.stdout
        assert "doctor" in result.stdout
        assert "map" in result.stdout

    def test_help_command_for_init(self, isolated_home) -> None:
        result = runner.invoke(app, ["help", "init"])
        assert result.exit_code == 0
        assert "--all-clients" in result.stdout
        assert "--cursor" in result.stdout

    def test_help_unknown_command(self, isolated_home) -> None:
        result = runner.invoke(app, ["help", "not-a-real-command"])
        assert result.exit_code == 1
        assert "Unknown command" in result.stdout

    def test_short_help_flag(self, isolated_home) -> None:
        result = runner.invoke(app, ["-h"])
        assert result.exit_code == 0
        assert "init" in result.stdout

    def test_map_command(self, isolated_home, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
        result = runner.invoke(app, ["map", "--workspace", str(tmp_path), "--json"])
        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "app.py" in result.stdout
