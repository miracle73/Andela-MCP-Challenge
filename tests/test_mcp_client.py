"""Live integration tests against the MCP server.

Skipped automatically if SKIP_LIVE_MCP=1 is set, so CI / offline runs stay green.
"""
import os
import pytest

from src.mcp_client import MCPClient

LIVE = os.getenv("SKIP_LIVE_MCP") != "1"
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not LIVE, reason="Live MCP tests disabled via SKIP_LIVE_MCP=1"),
]

URL = "https://order-mcp-74afyau24q-uc.a.run.app/mcp"


async def test_discovers_expected_tools():
    client = MCPClient(URL)
    tools = await client.discover_tools()
    names = {t["function"]["name"] for t in tools}
    expected = {
        "list_products", "get_product", "search_products",
        "get_customer", "verify_customer_pin",
        "list_orders", "get_order", "create_order",
    }
    assert expected.issubset(names), f"missing tools: {expected - names}"


async def test_verify_customer_pin_happy_path():
    client = MCPClient(URL)
    text, is_error = await client.call_tool(
        "verify_customer_pin",
        {"email": "donaldgarcia@example.net", "pin": "7912"},
    )
    assert is_error is False
    assert "Donald Garcia" in text
    assert "Customer ID:" in text


async def test_verify_customer_pin_wrong_pin_returns_error():
    client = MCPClient(URL)
    text, is_error = await client.call_tool(
        "verify_customer_pin",
        {"email": "donaldgarcia@example.net", "pin": "0000"},
    )
    assert is_error is True
    assert "not found" in text.lower() or "incorrect" in text.lower()


async def test_search_products_returns_results():
    client = MCPClient(URL)
    text, is_error = await client.call_tool("search_products", {"query": "monitor"})
    assert is_error is False
    assert "MON-" in text


async def test_get_unknown_product_returns_error():
    client = MCPClient(URL)
    text, is_error = await client.call_tool("get_product", {"sku": "DOES-NOT-EXIST-9999"})
    assert is_error is True
