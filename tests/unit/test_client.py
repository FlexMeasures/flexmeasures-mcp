"""ExtendedFlexMeasuresClient status handling, with the HTTP layer faked."""

from __future__ import annotations

import pytest

from flexmeasures_mcp.client import ExtendedFlexMeasuresClient, JobPending

UUID = "b3d26a8a-7a43-4a9f-93e1-fc2a869ea97b"


@pytest.fixture
async def fm_client():
    client = ExtendedFlexMeasuresClient(
        email="test@seita.nl",
        password="secret",
        host="test-host",
        ssl=False,
        access_token="dummy-token",
    )
    yield client
    await client.close()


def fake_request(fm_client, monkeypatch, payload, status, calls: list | None = None):
    async def _request(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return payload, status

    monkeypatch.setattr(fm_client, "request", _request)


async def test_polling_is_single_step(fm_client):
    """MCP tools must not block: the client never polls more than once."""
    assert fm_client.max_polling_steps == 1


async def test_trigger_forecast_accepts_202(fm_client, monkeypatch):
    calls: list = []
    fake_request(
        fm_client,
        monkeypatch,
        {"forecast": UUID, "job_id": UUID, "status": "ACCEPTED"},
        202,
        calls,
    )
    response = await fm_client.trigger_forecast(
        sensor_id=3, start="2026-07-13T00:00:00+02:00", duration="P2D"
    )
    assert response["forecast"] == UUID
    assert calls[0]["uri"] == "sensors/3/forecasts/trigger"
    # pandas normalizes the ISO duration (P2D -> P2DT0H0M0S)
    assert calls[0]["json_payload"]["duration"].startswith("P2D")


async def test_trigger_schedule_accepts_200_from_older_servers(
    fm_client, monkeypatch
):
    calls: list = []
    fake_request(
        fm_client, monkeypatch, {"schedule": UUID, "status": "PROCESSED"}, 200, calls
    )
    response = await fm_client.trigger_schedule(
        start="2026-07-13T00:00:00+02:00",
        duration="PT24H",
        asset_id=5,
        flex_model=[{"sensor": 12}],
    )
    assert response["schedule"] == UUID
    assert calls[0]["uri"] == "assets/5/schedules/trigger"
    assert calls[0]["json_payload"]["flex-model"] == [{"sensor": 12}]


async def test_trigger_schedule_rejects_other_statuses(fm_client, monkeypatch):
    fake_request(fm_client, monkeypatch, {"message": "nope"}, 405)
    with pytest.raises(ValueError, match="405"):
        await fm_client.trigger_schedule(
            start="2026-07-13T00:00:00+02:00", duration="PT24H", asset_id=5
        )


async def test_trigger_schedule_requires_exactly_one_target(fm_client):
    with pytest.raises(ValueError, match="either a sensor_id or an asset_id"):
        await fm_client.trigger_schedule(
            start="2026-07-13T00:00:00+02:00", duration="PT24H"
        )


async def test_get_forecast_pending_raises_jobpending(fm_client, monkeypatch):
    fake_request(
        fm_client, monkeypatch, {"status": "STARTED", "message": "job started"}, 202
    )
    with pytest.raises(JobPending) as excinfo:
        await fm_client.get_forecast(sensor_id=3, forecast_id=UUID)
    assert excinfo.value.status == "STARTED"


async def test_get_job_status(fm_client, monkeypatch):
    calls: list = []
    fake_request(
        fm_client, monkeypatch, {"status": "QUEUED", "message": "waiting"}, 200, calls
    )
    response = await fm_client.get_job_status(job_id=UUID)
    assert response["status"] == "QUEUED"
    assert calls[0]["uri"] == f"jobs/{UUID}"


async def test_add_automation_accepts_201(fm_client, monkeypatch):
    calls: list = []
    fake_request(fm_client, monkeypatch, {"id": 7, "type": "reports"}, 201, calls)
    response = await fm_client.add_automation(
        asset_id=5,
        automation={"type": "reports", "name": "r", "cronstr": "0 6 * * *"},
    )
    assert response["id"] == 7
    assert calls[0]["method"] == "POST"


async def test_delete_automation_accepts_204(fm_client, monkeypatch):
    fake_request(fm_client, monkeypatch, None, 204)
    await fm_client.delete_automation(asset_id=5, automation_id=7)
