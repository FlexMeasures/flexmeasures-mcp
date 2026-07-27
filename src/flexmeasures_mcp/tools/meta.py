"""Connection, health and (optionally) authentication tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import app_ctx, client
from flexmeasures_mcp.errors import map_fm_errors
from flexmeasures_mcp.tools import write_tool


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def health_check(ctx: Context) -> dict[str, Any]:
        """Check whether the FlexMeasures server is reachable and its core
        services (SQL database, and Redis job queues if configured) are ready.
        Call this first when something seems wrong."""
        c = client(ctx)
        versions = await c.get_versions()
        ready = await c.get_health_ready()
        return {
            "host": c.host,
            "flexmeasures_version": versions.get("server_version"),
            "api_versions": versions.get("server_supports_api_versions"),
            "services": ready,
        }

    @mcp.tool()
    @map_fm_errors
    async def connection_info(ctx: Context) -> dict[str, Any]:
        """Show who you are connected as: user, account and host. Use this to
        verify authentication and to learn the account ID for creating assets."""
        c = client(ctx)
        user = await c.get_user()
        account = await c.get_account()
        return {
            "host": c.host,
            "user": user,
            "account": account,
        }

    if settings.enable_auth_tool:

        @write_tool(mcp, settings)
        @map_fm_errors
        async def authenticate(email: str, password: str, ctx: Context) -> dict[str, Any]:
            """Swap the credentials this server uses for the FlexMeasures API
            and obtain a fresh access token. Only use when asked to act as a
            different user; credentials passed here end up in the conversation
            transcript."""
            c = client(ctx)
            c.email = email
            c.password = password
            c.access_token = None
            await c.get_access_token()
            user = await c.get_user()
            return {"authenticated": True, "user": user}
