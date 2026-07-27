"""Automation tools: recurring forecasts, schedules and reports.

Reports have no run-now API endpoint in FlexMeasures: they run only as cron
automations. These tools require a FlexMeasures server with automations
support (https://github.com/FlexMeasures/flexmeasures/pull/2288).
"""

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
    async def create_automation(
        asset_id: int,
        type: str,
        name: str,
        cronstr: str,
        ctx: Context,
        parameters: dict | None = None,
        generator: str | None = None,
        config: dict | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        """Create a recurring automation on an asset. type is one of
        "forecasts", "schedules" or "reports"; cronstr is a cron expression
        (e.g. "0 6 * * *" for daily at 06:00). parameters follow the type's
        schema: for schedules, a schedule-trigger message; for forecasts/
        reports, the generator's parameters. generator names a data generator
        class (required for reports, e.g. "PandasReporter"; forecasts default
        to "TrainPredictPipeline"). Requires delete-rights on the asset."""
        payload: dict = {
            "type": type,
            "name": name,
            "cronstr": cronstr,
            "active": active,
        }
        if parameters is not None:
            payload["parameters"] = parameters
        if generator is not None:
            payload["generator"] = generator
        if config is not None:
            payload["config"] = config
        return await client(ctx).add_automation(asset_id=asset_id, automation=payload)

    @write_tool(mcp, settings)
    @map_fm_errors
    async def create_report_automation(
        asset_id: int,
        name: str,
        cronstr: str,
        generator: str,
        parameters: dict,
        ctx: Context,
        config: dict | None = None,
    ) -> dict[str, Any]:
        """Create a recurring report on an asset (reports can ONLY run via
        cron automations - there is no run-now endpoint; the first results
        appear after the cron first fires). generator e.g. "PandasReporter";
        parameters define input/output sensors and the computation. Check
        results by reading the output sensor(s) with get_sensor_data."""
        payload = {
            "type": "reports",
            "name": name,
            "cronstr": cronstr,
            "generator": generator,
            "parameters": parameters,
            "active": True,
        }
        if config is not None:
            payload["config"] = config
        return await client(ctx).add_automation(asset_id=asset_id, automation=payload)

    @mcp.tool()
    @map_fm_errors
    async def list_automations(asset_id: int, ctx: Context) -> list[dict[str, Any]]:
        """List the automations configured on an asset."""
        return await client(ctx).get_automations(asset_id=asset_id)

    @mcp.tool()
    @map_fm_errors
    async def get_automation(asset_id: int, automation_id: int, ctx: Context) -> dict[str, Any]:
        """Fetch one automation, including its parameters, generator, a
        natural-language description of its recurrence, and job statistics."""
        return await client(ctx).get_automation(
            asset_id=asset_id, automation_id=automation_id
        )

    @write_tool(mcp, settings)
    @map_fm_errors
    async def update_automation(
        asset_id: int,
        automation_id: int,
        ctx: Context,
        name: str | None = None,
        cronstr: str | None = None,
        active: bool | None = None,
    ) -> dict[str, Any]:
        """Update an automation's name, cron schedule or active flag. Other
        fields (type, parameters, generator) are immutable - recreate the
        automation to change them."""
        updates = {
            k: v
            for k, v in {"name": name, "cronstr": cronstr, "active": active}.items()
            if v is not None
        }
        return await client(ctx).update_automation(
            asset_id=asset_id, automation_id=automation_id, updates=updates
        )

    if settings.enable_delete:

        @write_tool(mcp, settings)
        @map_fm_errors
        async def delete_automation(
            asset_id: int, automation_id: int, ctx: Context
        ) -> dict[str, Any]:
            """Delete an automation. Irreversible."""
            await client(ctx).delete_automation(
                asset_id=asset_id, automation_id=automation_id
            )
            return {"deleted": True, "automation_id": automation_id}
