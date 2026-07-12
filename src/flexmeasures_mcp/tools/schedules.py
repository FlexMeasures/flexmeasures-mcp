"""Scheduling tools: trigger a job, retrieve the resulting schedule."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors

NEXT_STEPS = (
    "Poll get_job_status(job_id=<schedule_id>) until status is FINISHED "
    "(FAILED includes exc_info explaining why), then call "
    "get_schedule(sensor_id=<power sensor>, schedule_id=<schedule_id>)."
)


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def trigger_schedule(
        start: str,
        duration: str,
        ctx: Context,
        asset_id: int | None = None,
        sensor_id: int | None = None,
        flex_model: dict | list[dict] | None = None,
        flex_context: dict | None = None,
        prior: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a scheduling job (e.g. optimize battery charging against
        prices). Pass asset_id (preferred; flex_model is then a list of
        per-device dicts, each with a "sensor" key) or sensor_id (single
        device). Example storage flex-model entry: {"sensor": 12,
        "soc-at-start": "0.2 MWh", "soc-min": "0 MWh", "soc-max": "0.9 MWh",
        "power-capacity": "0.5 MW"}. flex_context can be omitted when it is
        stored on the asset. Returns a schedule UUID immediately; the job runs
        asynchronously on a worker."""
        response = await client(ctx).trigger_schedule(
            start=start,
            duration=duration,
            flex_model=flex_model,
            flex_context=flex_context,
            sensor_id=sensor_id,
            asset_id=asset_id,
            prior=prior,
        )
        return {
            "schedule_id": response["schedule"],
            "job_id": response.get("job_id", response["schedule"]),
            "target": f"asset:{asset_id}" if asset_id else f"sensor:{sensor_id}",
            "next_steps": NEXT_STEPS,
        }

    @mcp.tool()
    @map_fm_errors
    async def get_schedule(
        sensor_id: int,
        schedule_id: str,
        ctx: Context,
        duration: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve the power schedule computed by a finished scheduling job,
        for one device's power sensor. Returns {values, start, duration, unit}.
        If the job is still running you get a pending result - poll
        get_job_status instead of retrying this in a tight loop. For multi-
        device schedules, call this once per device power sensor with the same
        schedule_id."""
        return await client(ctx).get_schedule(
            sensor_id=sensor_id, schedule_id=schedule_id, duration=duration
        )
