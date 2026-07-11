from __future__ import annotations

from fastmcp import FastMCP

from guider.logging_config import get_logger, setup_logging
from guider.mcp.prompts import register_prompts
from guider.mcp.resources import register_resources
from guider.mcp.tools import MCP_INSTRUCTIONS, register_tools
from guider.service import GuiderService

logger = get_logger("guider.mcp")


def create_mcp_server() -> FastMCP:
    setup_logging()
    mcp = FastMCP(
        name="AI Guider",
        instructions=MCP_INSTRUCTIONS,
    )
    service = GuiderService()
    register_tools(mcp, service)
    register_prompts(mcp, service)
    register_resources(mcp, service)
    logger.info("mcp_server_created", tools=25, prompts=3, resources=5)
    return mcp


def run_server() -> None:
    mcp = create_mcp_server()
    mcp.run()
