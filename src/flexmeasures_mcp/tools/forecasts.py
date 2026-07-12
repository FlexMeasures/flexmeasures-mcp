"""Forecasting tools: trigger a job, retrieve the resulting forecast."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def trigger_forecast(
        sensor_id: int,
        start: str,
        duration: str,
        ctx: Context,
        model: str | None = None,
        config: dict | None = None,
        prior: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a forecasting job for a sensor, forecasting from start (ISO
        8601) over duration (ISO 8601, e.g. "P2D"). The sensor needs enough
        historical data to train on. model defaults to the server's
        TrainPredictPipeline. Returns a forecast job UUID immediately; the job
        runs asynchronously on a worker."""
        response = await client(ctx).trigger_forecast(
            sensor_id=sensor_id,
            start=start,
            duration=duration,
            model=model,
            config=config,
            prior=prior,
        )
        return {
            "forecast_id": response["forecast"],
            "job_id": response.get("job_id", response["forecast"]),
            "sensor_id": sensor_id,
            "next_steps": (
                "Poll get_job_status(job_id=<forecast_id>) until FINISHED, then "
                "call get_forecast(sensor_id, forecast_id). If the job fanned "
                "out into multiple periods, get_forecast lists child job IDs to "
                "fetch individually."
            ),
        }

    @mcp.tool()
    @map_fm_errors
    async def get_forecast(sensor_id: int, forecast_id: str, ctx: Context) -> dict[str, Any]:
        """Retrieve the values produced by a finished forecasting job:
        {values, start, duration, unit}. While the job still runs you get a
        pending result; if it failed, the error explains why (e.g. not enough
        training data)."""
        return await client(ctx).get_forecast(
            sensor_id=sensor_id, forecast_id=forecast_id
        )
