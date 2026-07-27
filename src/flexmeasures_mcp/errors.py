"""Map FlexMeasures API errors to agent-actionable MCP tool errors."""

from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable

import aiohttp
from mcp.server.fastmcp.exceptions import ToolError

from flexmeasures_mcp.client import JobPending

PENDING_MARKERS = (
    "Scheduling job waiting",
    "Scheduling job in progress",
    "Scheduling job has an unknown status",
)


def _pending_result(message: str, status: str | None = None) -> dict:
    return {
        "status": status or "PENDING",
        "pending": True,
        "hint": (
            "The job is still running. Poll get_job_status(job_id=<uuid>) - it "
            "always returns the job state (QUEUED/STARTED/FINISHED/FAILED) - "
            "then fetch the result once FINISHED."
        ),
        "message": message,
    }


def map_fm_errors(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Wrap an MCP tool: turn client/API exceptions into helpful ToolErrors,
    and job-still-pending conditions into a structured pending result."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except JobPending as e:
            return _pending_result(str(e), status=e.status)
        except aiohttp.ContentTypeError as e:
            raise ToolError(
                f"Unexpected (non-JSON) response from the FlexMeasures server: {e}"
            ) from e
        except aiohttp.ClientResponseError as e:
            raise ToolError(_describe_http_error(e.status, e.message)) from e
        except (aiohttp.ClientConnectorError, ConnectionError) as e:
            raise ToolError(
                f"Cannot reach the FlexMeasures server: {e}. "
                "Check FLEXMEASURES_HOST and FLEXMEASURES_SSL."
            ) from e
        except ValueError as e:
            message = str(e)
            if any(marker in message for marker in PENDING_MARKERS):
                # older servers report a pending schedule via 400 UNKNOWN_SCHEDULE
                return _pending_result(message)
            raise ToolError(message) from e

    return wrapper


def _describe_http_error(status: int, message: str) -> str:
    if status == 401:
        return (
            "Authentication failed (401). Check FLEXMEASURES_EMAIL and "
            "FLEXMEASURES_PASSWORD; if you use FLEXMEASURES_ACCESS_TOKEN it may "
            "have expired (tokens cannot be refreshed without credentials)."
        )
    if status == 403:
        return (
            "Forbidden (403): the entity likely belongs to another account, or "
            "your user lacks the required permission. Use list_assets/"
            "list_sensors to see what your account can access."
        )
    if status == 404:
        return (
            "Not found (404): check the ID - the entity may have been deleted, "
            "or it belongs to a different FlexMeasures instance."
        )
    if status == 422:
        return (
            f"Validation failed (422): {message}. Fix the listed fields; for "
            "flex-model/flex-context fields, see the flexmeasures://docs/"
            "flex-model resource."
        )
    if status == 503:
        return (
            "Job queues unavailable (503): the FlexMeasures instance may be "
            "running without Redis/workers, so jobs cannot run."
        )
    return f"FlexMeasures API error ({status}): {message}"
