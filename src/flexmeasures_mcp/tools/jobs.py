"""Job status tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import client
from flexmeasures_mcp.errors import map_fm_errors


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    @map_fm_errors
    async def get_job_status(job_id: str, ctx: Context) -> dict[str, Any]:
        """Check any background job (scheduling or forecasting) by UUID. The
        uniform way to poll: returns status (QUEUED/STARTED/FINISHED/FAILED/
        DEFERRED), timestamps, the job result (for finished scheduling jobs
        this includes soft SoC constraint analysis) and exc_info for failed
        jobs. Poll every few seconds until FINISHED or FAILED."""
        return await client(ctx).get_job_status(job_id=job_id)

    @mcp.tool()
    @map_fm_errors
    async def list_asset_jobs(asset_id: int, ctx: Context) -> dict[str, Any]:
        """List recent background jobs (forecasting/scheduling) related to an
        asset - useful to find job UUIDs you lost or to diagnose failures."""
        return await client(ctx).get_asset_jobs(asset_id=asset_id)
