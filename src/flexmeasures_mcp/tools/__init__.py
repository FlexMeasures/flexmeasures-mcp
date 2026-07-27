"""Registration helpers shared by the tool modules."""

from __future__ import annotations

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from flexmeasures_mcp.config import Settings


def write_tool(mcp: FastMCP, settings: Settings) -> Callable:
    """Like ``mcp.tool()``, but skips registration in read-only mode.

    Use for every tool that mutates server state: creating, updating or
    deleting entities, posting data, or triggering jobs.
    """
    if settings.read_only:
        return lambda fn: fn
    return mcp.tool()
