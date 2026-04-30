"""Async MCP client wrapper.

Wraps the official `mcp` Python SDK over Streamable HTTP. Exposes:
- `discover_tools()` — list MCP tools and convert to OpenAI tool schemas.
- `call_tool(name, args)` — invoke a tool and return a plain-string result.

The client owns its own session lifecycle. We open a fresh session per
request rather than holding one open across the entire chat — that keeps
the server stateless from our side and tolerates Cloud Run idle restarts.
"""
from __future__ import annotations

import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


def _mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    """Translate an MCP tool definition into an OpenAI tool schema."""
    schema = tool.inputSchema or {"type": "object", "properties": {}}
    description = (tool.description or "").strip()
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": description[:1024],
            "parameters": schema,
        },
    }


def _extract_text(result: Any) -> str:
    """Pull plain text out of an MCP CallToolResult."""
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    if not parts and getattr(result, "structuredContent", None):
        sc = result.structuredContent
        if isinstance(sc, dict) and "result" in sc:
            parts.append(str(sc["result"]))
    return "\n".join(parts).strip() or "(empty response)"


class MCPClient:
    """Thin async wrapper over the MCP Streamable HTTP client."""

    def __init__(self, server_url: str) -> None:
        self.server_url = server_url

    async def discover_tools(self) -> list[dict[str, Any]]:
        async with streamablehttp_client(self.server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                tools = [_mcp_tool_to_openai(t) for t in tools_response.tools]
                logger.info(
                    "mcp.tools.discovered",
                    extra={"extra_fields": {"count": len(tools), "names": [t["function"]["name"] for t in tools]}},
                )
                return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """Invoke a tool. Returns (text, is_error)."""
        async with streamablehttp_client(self.server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=arguments)
                is_error = bool(getattr(result, "isError", False))
                text = _extract_text(result)
                logger.info(
                    "mcp.tool.called",
                    extra={"extra_fields": {"tool": name, "is_error": is_error, "args": arguments}},
                )
                return text, is_error
