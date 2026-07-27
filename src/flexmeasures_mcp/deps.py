"""Shared lifespan context and accessors for tool implementations."""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.fastmcp import Context

from flexmeasures_mcp.client import ExtendedFlexMeasuresClient
from flexmeasures_mcp.config import Settings


@dataclass
class AppContext:
    client: ExtendedFlexMeasuresClient
    settings: Settings


def app_ctx(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context


def client(ctx: Context) -> ExtendedFlexMeasuresClient:
    return app_ctx(ctx).client
