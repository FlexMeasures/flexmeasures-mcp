"""Sensor tools: CRUD."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def list_sensors(ctx: Context, asset_id: int | None = None) -> list[dict[str, Any]]:
        """List sensors accessible to the connected user, optionally only those
        under one asset (and its sub-assets)."""
        return await client(ctx).get_sensors(
            asset_id=asset_id, parse_json_fields=True
        )

    @mcp.tool()
    @map_fm_errors
    async def get_sensor(sensor_id: int, ctx: Context) -> dict[str, Any]:
        """Fetch one sensor (unit, event resolution, timezone, attributes)."""
        return await client(ctx).get_sensor(
            sensor_id=sensor_id, parse_json_fields=True
        )

    @mcp.tool()
    @map_fm_errors
    async def create_sensor(
        name: str,
        unit: str,
        event_resolution: str,
        generic_asset_id: int,
        ctx: Context,
        timezone: str | None = None,
        attributes: dict | None = None,
    ) -> dict[str, Any]:
        """Create a sensor on an asset. Every time series in FlexMeasures lives
        on a sensor. unit examples: "kW", "MW", "EUR/MWh", "%".
        event_resolution is an ISO 8601 duration, e.g. "PT15M" for 15-minute
        values ("PT0H" for instantaneous). timezone is an IANA name like
        "Europe/Amsterdam" (defaults to the server timezone)."""
        return await client(ctx).add_sensor(
            name=name,
            event_resolution=event_resolution,
            unit=unit,
            generic_asset_id=generic_asset_id,
            timezone=timezone,
            attributes=attributes,
        )
