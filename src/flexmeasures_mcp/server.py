"""FastMCP server wiring: lifespan, tool/prompt/resource registration."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from importlib.metadata import entry_points

from mcp.server.fastmcp import FastMCP

from flexmeasures_mcp.client import ExtendedFlexMeasuresClient
from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.deps import AppContext

logger = logging.getLogger(__name__)

# Placeholders keep the base client's dataclass validation happy in
# token-only mode; re-authentication then fails with a clear 401 message.
TOKEN_ONLY_EMAIL = "token-only@flexmeasures-mcp.invalid"
TOKEN_ONLY_PASSWORD = "token-only"  # noqa: S105


def default_client_factory(settings: Settings) -> ExtendedFlexMeasuresClient:
    return ExtendedFlexMeasuresClient(
        email=settings.email or TOKEN_ONLY_EMAIL,
        password=settings.password or TOKEN_ONLY_PASSWORD,
        host=settings.host,
        ssl=settings.use_ssl,
        access_token=settings.access_token,
    )


def create_server(
    settings: Settings | None = None,
    client_factory: Callable[[Settings], ExtendedFlexMeasuresClient] | None = None,
) -> FastMCP:
    settings = settings or Settings()
    client_factory = client_factory or default_client_factory

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
        client = client_factory(settings)
        try:
            yield AppContext(client=client, settings=settings)
        finally:
            await client.close()

    mcp = FastMCP(
        "FlexMeasures",
        instructions=(
            "Build and operate FlexMeasures energy-flexibility sites: create "
            "assets and sensors, post time-series data, trigger forecasting "
            "and scheduling jobs, poll job status, retrieve results, and "
            "manage report/forecast/schedule automations. Jobs run "
            "asynchronously on workers: trigger tools return a job UUID; poll "
            "get_job_status until FINISHED, then fetch results."
        ),
        lifespan=lifespan,
    )

    _register_all(mcp, settings)
    return mcp


def _register_all(mcp: FastMCP, settings: Settings) -> None:
    from flexmeasures_mcp import prompts, resources
    from flexmeasures_mcp.tools import (
        assets,
        automations,
        data,
        forecasts,
        jobs,
        meta,
        schedules,
        sensors,
    )

    for module in (meta, assets, sensors, data, forecasts, schedules, jobs):
        module.register(mcp, settings)
    automations.register(mcp, settings)
    prompts.register(mcp, settings)
    resources.register(mcp, settings)

    # Extension point: third-party packages can add tools via entry points.
    for ep in entry_points(group="flexmeasures_mcp.tools"):
        try:
            ep.load()(mcp, settings)
            logger.info("Loaded flexmeasures_mcp.tools plugin: %s", ep.name)
        except Exception:  # noqa: BLE001 - a broken plugin must not kill the server
            logger.exception("Failed to load flexmeasures_mcp.tools plugin %s", ep.name)
