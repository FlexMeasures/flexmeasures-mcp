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

# The read surface: tool names track the stable OpenAPI operationIds, so reads
# are list_* / get_*, except for these two.
READ_TOOL_PREFIXES = ("list_", "get_")
READ_TOOL_NAMES = frozenset({"health_check", "connection_info"})


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

    if settings.read_only and (settings.enable_delete or settings.enable_auth_tool):
        logger.warning(
            "Read-only mode wins over FLEXMEASURES_MCP_ENABLE_DELETE / "
            "FLEXMEASURES_MCP_ENABLE_AUTH_TOOL: no mutating tools are exposed."
        )

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
        client = client_factory(settings)
        try:
            yield AppContext(client=client, settings=settings)
        finally:
            await client.close()

    if settings.read_only:
        instructions = (
            "Inspect FlexMeasures energy-flexibility sites: browse assets and "
            "sensors, read time-series data, retrieve forecasts and schedules, "
            "check job status, and review automations. This server runs in "
            "read-only mode: no tools that create, change or trigger anything "
            "are available - recommend such actions to the user instead of "
            "attempting them."
        )
    else:
        instructions = (
            "Build and operate FlexMeasures energy-flexibility sites: create "
            "assets and sensors, post time-series data, trigger forecasting "
            "and scheduling jobs, poll job status, retrieve results, and "
            "manage report/forecast/schedule automations. Jobs run "
            "asynchronously on workers: trigger tools return a job UUID; poll "
            "get_job_status until FINISHED, then fetch results."
        )

    mcp = FastMCP(
        "FlexMeasures",
        instructions=instructions,
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

    # Last, so it also covers plugin tools.
    if settings.read_only:
        _prune_to_read_surface(mcp)


def _prune_to_read_surface(mcp: FastMCP) -> None:
    """Drop every registered tool outside the documented read surface.

    ``write_tool`` already stops the built-in mutating tools from being
    registered, but it is opt-in: a core tool that forgets the decorator, or a
    plugin that never looks at ``settings.read_only``, would still be served.
    Pruning once, after everything has registered, makes read-only hold by
    construction instead of by discipline. Anything dropped here is a bug or a
    careless plugin, so each removal is logged.

    The trade-off is that this makes the naming convention load-bearing: a read
    tool named outside list_*/get_* is dropped in read-only mode. Tool names
    follow the stable OpenAPI operationIds, so that is a deliberate choice.
    """
    # remove_tool is public API; only the synchronous listing is not.
    for tool in list(mcp._tool_manager.list_tools()):  # noqa: SLF001
        if tool.name.startswith(READ_TOOL_PREFIXES) or tool.name in READ_TOOL_NAMES:
            continue
        mcp.remove_tool(tool.name)
        logger.warning(
            "Read-only mode: removed tool %s, which is not part of the read "
            "surface. Mutating tools should be declared with "
            "flexmeasures_mcp.tools.write_tool.",
            tool.name,
        )
