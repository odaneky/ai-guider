"""Tests for MCP server."""

from guider.mcp.server import create_mcp_server


class TestMCPServer:
    def test_create_server(self) -> None:
        mcp = create_mcp_server()
        assert mcp.name == "AI Guider"

    def test_server_has_instructions(self) -> None:
        mcp = create_mcp_server()
        assert "govern_request" in (mcp.instructions or "")
