"""Mapping FlexMeasures failures to MCP-friendly results and errors."""

from __future__ import annotations

from types import SimpleNamespace

import aiohttp
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from flexmeasures_mcp.client import JobPending
from flexmeasures_mcp.errors import _describe_http_error, map_fm_errors


async def test_job_pending_becomes_structured_result():
    @map_fm_errors
    async def tool():
        raise JobPending("still busy", status="STARTED")

    result = await tool()

    assert result["pending"] is True
    assert result["status"] == "STARTED"
    assert "get_job_status" in result["hint"]


async def test_older_pending_schedule_error_becomes_structured_result():
    @map_fm_errors
    async def tool():
        raise ValueError("Scheduling job in progress. StorageScheduler was used.")

    result = await tool()

    assert result["pending"] is True
    assert result["status"] == "PENDING"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "Authentication failed"),
        (403, "Forbidden"),
        (404, "Not found"),
        (422, "Validation failed"),
        (503, "Job queues unavailable"),
        (500, "FlexMeasures API error"),
    ],
)
def test_http_error_descriptions(status, expected):
    assert expected in _describe_http_error(status, "bad input")


async def test_client_response_error_becomes_tool_error():
    @map_fm_errors
    async def tool():
        raise aiohttp.ClientResponseError(
            request_info=None, history=(), status=404, message="missing"
        )

    with pytest.raises(ToolError, match="Not found"):
        await tool()


async def test_connection_error_becomes_tool_error():
    @map_fm_errors
    async def tool():
        raise ConnectionError("refused")

    with pytest.raises(ToolError, match="Cannot reach"):
        await tool()


async def test_content_type_error_becomes_tool_error():
    @map_fm_errors
    async def tool():
        raise aiohttp.ContentTypeError(
            request_info=SimpleNamespace(real_url="http://test-host"),
            history=(),
            message="text/html",
        )

    with pytest.raises(ToolError, match="non-JSON"):
        await tool()


async def test_other_value_error_becomes_tool_error():
    @map_fm_errors
    async def tool():
        raise ValueError("invalid field")

    with pytest.raises(ToolError, match="invalid field"):
        await tool()
