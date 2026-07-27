"""Asset tools: types, CRUD."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors
from flexmeasures_mcp.tools import write_tool


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def list_asset_types(ctx: Context) -> list[dict[str, Any]]:
        """List the available asset types (e.g. site, battery, solar, evse).
        You need an asset type ID to create an asset."""
        return await client(ctx).get_asset_types()

    @mcp.tool()
    @map_fm_errors
    async def list_assets(
        ctx: Context,
        account_id: int | None = None,
        include_public: bool = False,
    ) -> list[dict[str, Any]]:
        """List assets accessible to the connected user (optionally for another
        account you may read, and optionally including public assets)."""
        kwargs = {}
        if account_id is not None:
            kwargs["account_id"] = account_id
        return await client(ctx).get_assets(
            include_public=include_public, parse_json_fields=True, **kwargs
        )

    @mcp.tool()
    @map_fm_errors
    async def get_asset(asset_id: int, ctx: Context) -> dict[str, Any]:
        """Fetch one asset, including its attributes, flex-context and
        flex-model (parsed from JSON)."""
        return await client(ctx).get_asset(asset_id=asset_id, parse_json_fields=True)

    @write_tool(mcp, settings)
    @map_fm_errors
    async def create_asset(
        name: str,
        generic_asset_type_id: int,
        ctx: Context,
        account_id: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        parent_asset_id: int | None = None,
        attributes: dict | None = None,
        flex_context: dict | None = None,
    ) -> dict[str, Any]:
        """Create an asset (a site, building, battery, ...). Use
        list_asset_types for type IDs and connection_info for your account ID.
        Set parent_asset_id to build a hierarchy (e.g. battery under a site).
        The flex_context can reference price sensors, e.g.
        {"consumption-price": {"sensor": 9}}."""
        c = client(ctx)
        if account_id is None:
            account = await c.get_account()
            account_id = account["id"] if account else None
        extra: dict = {}
        if parent_asset_id is not None:
            extra["parent_asset_id"] = parent_asset_id
        if attributes is not None:
            extra["attributes"] = attributes
        if flex_context is not None:
            extra["flex_context"] = flex_context
        return await c.add_asset(
            name=name,
            account_id=account_id,
            latitude=latitude,
            longitude=longitude,
            generic_asset_type_id=generic_asset_type_id,
            **extra,
        )

    @write_tool(mcp, settings)
    @map_fm_errors
    async def update_asset(asset_id: int, updates: dict, ctx: Context) -> dict[str, Any]:
        """Update fields of an asset, e.g. {"name": ..., "attributes": {...},
        "flex_context": {...}}. Returns the updated asset."""
        return await client(ctx).update_asset(asset_id=asset_id, updates=updates)

    if settings.enable_delete:

        @write_tool(mcp, settings)
        @map_fm_errors
        async def delete_asset(asset_id: int, ctx: Context) -> dict[str, Any]:
            """Delete an asset and all data on its sensors. Irreversible."""
            await client(ctx).delete_asset(asset_id=asset_id, confirm_first=False)
            return {"deleted": True, "asset_id": asset_id}
