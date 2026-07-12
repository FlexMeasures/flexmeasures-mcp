"""Tool behavior against a mocked FlexMeasures client."""

from __future__ import annotations

import aiohttp

SCHEDULE_UUID = "364bfd06-c1fa-430b-8d25-8f5a547651fb"


async def test_trigger_schedule_returns_ids_and_next_steps(make_session, mock_client):
    mock_client.trigger_schedule.return_value = {
        "schedule": SCHEDULE_UUID,
        "job_id": SCHEDULE_UUID,
        "status": "ACCEPTED",
    }
    async with make_session() as session:
        result = await session.call_tool(
            "trigger_schedule",
            {
                "asset_id": 5,
                "start": "2026-07-13T00:00:00+02:00",
                "duration": "PT24H",
                "flex_model": [{"sensor": 12, "soc-at-start": "0 kWh"}],
            },
        )
    assert not result.isError
    data = result.structuredContent
    assert data["schedule_id"] == SCHEDULE_UUID
    assert data["job_id"] == SCHEDULE_UUID
    assert data["target"] == "asset:5"
    assert "get_job_status" in data["next_steps"]
    kwargs = mock_client.trigger_schedule.call_args.kwargs
    assert kwargs["asset_id"] == 5 and kwargs["sensor_id"] is None


async def test_get_schedule_pending_is_not_an_error(make_session, mock_client):
    mock_client.get_schedule.side_effect = ValueError(
        "Scheduling job in progress. StorageScheduler was used."
    )
    async with make_session() as session:
        result = await session.call_tool(
            "get_schedule", {"sensor_id": 12, "schedule_id": SCHEDULE_UUID}
        )
    assert not result.isError
    assert result.structuredContent["pending"] is True
    assert "get_job_status" in result.structuredContent["hint"]


async def test_forbidden_maps_to_actionable_error(make_session, mock_client):
    mock_client.get_asset.side_effect = aiohttp.ClientResponseError(
        request_info=None, history=(), status=403, message="INVALID_SENDER"
    )
    async with make_session() as session:
        result = await session.call_tool("get_asset", {"asset_id": 999})
    assert result.isError
    text = result.content[0].text
    assert "Forbidden" in text and "another account" in text


async def test_get_job_status_passthrough(make_session, mock_client):
    payload = {
        "status": "FINISHED",
        "message": "Scheduling job has finished.",
        "result": {"unresolved": [], "resolved": []},
        "exc_info": None,
    }
    mock_client.get_job_status.return_value = payload
    async with make_session() as session:
        result = await session.call_tool("get_job_status", {"job_id": SCHEDULE_UUID})
    assert not result.isError
    assert result.structuredContent == payload


async def test_create_report_automation_builds_payload(make_session, mock_client):
    mock_client.add_automation.return_value = {"id": 1, "type": "reports"}
    async with make_session() as session:
        result = await session.call_tool(
            "create_report_automation",
            {
                "asset_id": 5,
                "name": "daily energy report",
                "cronstr": "0 6 * * *",
                "generator": "PandasReporter",
                "parameters": {"input": [], "output": []},
            },
        )
    assert not result.isError
    payload = mock_client.add_automation.call_args.kwargs["automation"]
    assert payload["type"] == "reports"
    assert payload["generator"] == "PandasReporter"
    assert payload["cronstr"] == "0 6 * * *"
