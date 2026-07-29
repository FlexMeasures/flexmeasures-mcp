"""Time-series data tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors
from flexmeasures_mcp.tools import write_tool


def register(mcp: FastMCP, settings: Settings) -> None:
    @write_tool(mcp, settings)
    @map_fm_errors
    async def post_sensor_data(
        sensor_id: int,
        values: list[float],
        start: str,
        duration: str,
        unit: str,
        ctx: Context,
        prior: str | None = None,
    ) -> dict[str, Any]:
        """Post equally-spaced time-series values to a sensor (measurements,
        prices, or forecast inputs). start is ISO 8601 with timezone offset
        (e.g. "2026-07-13T00:00:00+02:00"), duration an ISO 8601 duration
        covering all values (e.g. "PT24H" for 24 hourly values). The unit must
        be convertible to the sensor's unit. Set prior (ISO 8601 datetime) to
        record when these values were known, e.g. for historical forecasts."""
        await client(ctx).post_sensor_data(
            sensor_id=sensor_id,
            start=start,
            duration=duration,
            values=values,
            unit=unit,
            prior=prior,
        )
        return {
            "posted": True,
            "sensor_id": sensor_id,
            "n_values": len(values),
            "start": start,
            "duration": duration,
            "unit": unit,
        }

    @mcp.tool()
    @map_fm_errors
    async def get_sensor_data(
        sensor_id: int,
        start: str,
        duration: str,
        unit: str,
        resolution: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Read time-series data from a sensor. Returns {values, start,
        duration, unit}; null values mark gaps. resolution must be a multiple
        of the sensor's event resolution (e.g. "PT1H"); the unit must be
        convertible from the sensor's unit."""
        return await client(ctx).get_sensor_data(
            sensor_id=sensor_id,
            start=start,
            duration=duration,
            unit=unit,
            resolution=resolution,
        )
