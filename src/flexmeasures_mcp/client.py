"""Extended FlexMeasures API client.

Subclasses the async ``flexmeasures-client`` and adds the endpoints an MCP
server needs that the upstream client does not cover yet (forecast trigger and
retrieval, generic job status, asset jobs, automations CRUD, health).
The new methods are candidates for upstreaming to flexmeasures-client.

Async job semantics: FlexMeasures returns 202 (Accepted) when it enqueues a
job (and, from API v3.0-32 on, also while polling an unfinished schedule).
Older servers signal "schedule not ready" with a 400 UNKNOWN_SCHEDULE, which
the base client turns into polling; we configure single-step polling so MCP
tools return quickly instead of blocking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from flexmeasures_client import FlexMeasuresClient

#: statuses that signal an accepted (enqueued) asynchronous job
ACCEPTED_STATUSES = (200, 202)


class JobPending(Exception):
    """The asynchronous job exists but has not finished yet."""

    def __init__(self, message: str, status: str | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class ExtendedFlexMeasuresClient(FlexMeasuresClient):
    """FlexMeasuresClient plus forecasts, jobs, automations and health."""

    def __post_init__(self):
        # MCP tools must not block: never poll more than once
        self.max_polling_steps = 1
        super().__post_init__()

    # -- scheduling (override: accept 202 from API v3.0-32, keep 200 for older servers)

    async def trigger_schedule(  # type: ignore[override]
        self,
        start: str | datetime,
        duration: str | timedelta,
        flex_model: dict | list[dict] | None = None,
        flex_context: dict | None = None,
        sensor_id: int | None = None,
        asset_id: int | None = None,
        prior: str | datetime | None = None,
    ) -> dict:
        """Trigger a scheduling job; returns the response body (with the job UUID
        under both "schedule" and, on newer servers, "job_id")."""
        if (sensor_id is None) == (asset_id is None):
            raise ValueError("Pass either a sensor_id or an asset_id.")
        message: dict = {
            "start": pd.Timestamp(start).isoformat(),
            "duration": pd.Timedelta(duration).isoformat(),
        }
        if flex_model is not None:
            message["flex-model"] = flex_model
        if flex_context is not None:
            message["flex-context"] = flex_context
        if prior is not None:
            message["prior"] = pd.Timestamp(prior).isoformat()

        if sensor_id is not None:
            uri = f"sensors/{sensor_id}/schedules/trigger"
        else:
            uri = f"assets/{asset_id}/schedules/trigger"
        response, status = await self.request(uri=uri, json_payload=message)
        self._check_accepted(status)
        if not isinstance(response, dict) or not isinstance(
            response.get("schedule"), str
        ):
            raise ValueError(f"Expected a schedule ID, but got: {response}")
        return response

    # -- forecasting

    async def trigger_forecast(
        self,
        sensor_id: int,
        start: str | datetime,
        duration: str | timedelta,
        model: str | None = None,
        config: dict | None = None,
        prior: str | datetime | None = None,
    ) -> dict:
        """Trigger a forecasting job; returns the response body (with the job UUID
        under both "forecast" and, on newer servers, "job_id")."""
        message: dict = {
            "start": pd.Timestamp(start).isoformat(),
            "duration": pd.Timedelta(duration).isoformat(),
        }
        if model is not None:
            message["model"] = model
        if config is not None:
            message["config"] = config
        if prior is not None:
            message["prior"] = pd.Timestamp(prior).isoformat()
        response, status = await self.request(
            uri=f"sensors/{sensor_id}/forecasts/trigger",
            json_payload=message,
        )
        self._check_accepted(status)
        if not isinstance(response, dict) or not isinstance(
            response.get("forecast"), str
        ):
            raise ValueError(f"Expected a forecast job ID, but got: {response}")
        return response

    async def get_forecast(self, sensor_id: int, forecast_id: str) -> dict:
        """Get forecast results. Raises JobPending while the job is unfinished."""
        response, status = await self.request(
            uri=f"sensors/{sensor_id}/forecasts/{forecast_id}",
            method="GET",
        )
        if status == 202:
            raise JobPending(
                response.get("message", "Forecasting job still in progress."),
                status=response.get("status"),
            )
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    # -- jobs

    async def get_job_status(self, job_id: str) -> dict:
        """Get the status of any background job (scheduling, forecasting, ...)."""
        response, status = await self.request(uri=f"jobs/{job_id}", method="GET")
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    async def get_asset_jobs(self, asset_id: int) -> dict:
        """List background jobs related to an asset."""
        response, status = await self.request(
            uri=f"assets/{asset_id}/jobs", method="GET"
        )
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    # -- automations (requires a FlexMeasures server with automations support)

    async def get_automations(self, asset_id: int) -> list | dict:
        response, status = await self.request(
            uri=f"assets/{asset_id}/automations", method="GET"
        )
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    async def get_automation(self, asset_id: int, automation_id: int) -> dict:
        response, status = await self.request(
            uri=f"assets/{asset_id}/automations/{automation_id}", method="GET"
        )
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    async def add_automation(self, asset_id: int, automation: dict) -> dict:
        response, status = await self.request(
            uri=f"assets/{asset_id}/automations",
            method="POST",
            json_payload=automation,
        )
        if status not in (200, 201):
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    async def update_automation(
        self, asset_id: int, automation_id: int, updates: dict
    ) -> dict:
        response, status = await self.request(
            uri=f"assets/{asset_id}/automations/{automation_id}",
            method="PATCH",
            json_payload=updates,
        )
        if status != 200:
            raise ValueError(f"Request failed with status code {status}: {response}")
        return response

    async def delete_automation(self, asset_id: int, automation_id: int) -> None:
        _response, status = await self.request(
            uri=f"assets/{asset_id}/automations/{automation_id}",
            method="DELETE",
        )
        if status not in (200, 204):
            raise ValueError(f"Request failed with status code {status}")

    # -- health

    async def get_health_ready(self) -> dict:
        response, _status = await self.request(
            uri="health/ready", method="GET", include_auth=False
        )
        return response

    # -- helpers

    @staticmethod
    def _check_accepted(status: int) -> None:
        if status not in ACCEPTED_STATUSES:
            raise ValueError(f"Request failed with status code {status}")
