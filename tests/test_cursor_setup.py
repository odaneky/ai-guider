"""Tests for Cursor setup helpers."""

from guider.cursor_setup import CURSOR_RULE_CONTENT, setup_cursor


class TestCursorSetup:
    def test_setup_cursor_writes_files(self, tmp_path) -> None:
        mcp_path = tmp_path / "mcp.json"
        rule_path = tmp_path / "rules" / "ai-guider.mdc"
        result = setup_cursor(mcp_config_path=mcp_path, rules_path=rule_path)

        assert mcp_path.exists()
        assert rule_path.exists()
        assert "ai-guider" in mcp_path.read_text()
        assert "govern_request" in rule_path.read_text()
        assert result["command"]

    def test_setup_cursor_hooks(self, tmp_path) -> None:
        from guider.cursor_setup import setup_cursor_hooks

        cursor = tmp_path / ".cursor"
        result = setup_cursor_hooks(cursor)
        assert (cursor / "hooks.json").exists()
        assert "ai-guider-session" in (cursor / "hooks.json").read_text()
        assert (cursor / "hooks" / "ai-guider-session.sh").exists()
        assert result["hooks_json"]
