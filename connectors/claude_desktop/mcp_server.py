"""Claude Desktop stdio MCP bridge for memward.

Exposes save_memory and search_memory tools over stdio and forwards
requests to the running memward core API (http://127.0.0.1:8000).
"""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = "http://127.0.0.1:8000"

mcp = FastMCP("memward")


@mcp.tool()
def save_memory(content: str, source: str = "claude_desktop") -> dict[str, Any]:
    """Save a concise fact/decision/preference to memward memory."""
    payload = {"content": content, "source": source}
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(f"{BASE_URL}/mcp/save_memory", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def search_memory(query: str, limit: int = 5) -> dict[str, Any]:
    """Search approved memories relevant to the query."""
    params = {"query": query, "limit": limit}
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{BASE_URL}/mcp/search_memory", params=params)
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
