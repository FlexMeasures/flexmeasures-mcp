"""Tool behavior against a mocked FlexMeasures client."""

from __future__ import annotations

import aiohttp

SCHEDULE_UUID = "364bfd06-c1fa-430b-8d25-8f5a547651fb"


async def test_health_and_connection_info(make_session, mock_client):
    mock_client.get_versions.return_value = {
        "server_version": "3.0",
        "server_supports_api_versions": ["3_0"],
    }
    mock_client.get_health_ready.return_value = {"database": "ok"}
    mock_client.get_user.return_value = {"id": 3}
    mock_client.get_account.return_value = {"id": 1}

    async with make_session() as session:
        health = await session.call_tool("health_check", {})
        info = await session.call_tool("connection_info", {})

    assert health.structuredContent == {
        "host": "test-host",
        "flexmeasures_version": "3.0",
        "api_versions": ["3_0"],
        "services": {"database": "ok"},
    }
    assert info.structuredContent == {
        "host": "test-host",
        "user": {"id": 3},
        "account": {"id": 1},
    }


async def test_asset_tools_pass_expected_options(make_session, mock_client):
    mock_client.get_asset_types.return_value = [{"id": 1, "name": "site"}]
    mock_client.get_assets.return_value = [{"id": 2}]
    mock_client.get_account.return_value = {"id": 1}
    mock_client.add_asset.return_value = {"id": 3}
    mock_client.update_asset.return_value = {"id": 3, "name": "updated"}

    async with make_session() as session:
        asset_types = await session.call_tool("list_asset_types", {})
        assets = await session.call_tool(
            "list_assets", {"account_id": 1, "include_public": True}
        )
        created = await session.call_tool(
            "create_asset",
            {
                "name": "battery",
                "generic_asset_type_id": 2,
                "latitude": 52.0,
                "longitude": 5.0,
                "parent_asset_id": 10,
                "attributes": {"capacity": "900 kWh"},
                "flex_context": {"consumption-price": {"sensor": 9}},
            },
        )
        updated = await session.call_tool(
            "update_asset", {"asset_id": 3, "updates": {"name": "updated"}}
        )

    assert asset_types.structuredContent["result"] == [{"id": 1, "name": "site"}]
    assert assets.structuredContent["result"] == [{"id": 2}]
    assert created.structuredContent == {"id": 3}
    assert updated.structuredContent == {"id": 3, "name": "updated"}
    mock_client.get_assets.assert_awaited_once_with(
        include_public=True,
        parse_json_fields=True,
        account_id=1,
    )
    mock_client.add_asset.assert_awaited_once_with(
        name="battery",
        account_id=1,
        latitude=52.0,
        longitude=5.0,
        generic_asset_type_id=2,
        parent_asset_id=10,
        attributes={"capacity": "900 kWh"},
        flex_context={"consumption-price": {"sensor": 9}},
    )


async def test_sensor_data_forecast_and_job_tools(make_session, mock_client):
    mock_client.get_sensors.return_value = [{"id": 1}]
    mock_client.get_sensor.return_value = {"id": 1}
    mock_client.add_sensor.return_value = {"id": 2}
    mock_client.get_sensor_data.return_value = {"values": [1.0]}
    mock_client.trigger_forecast.return_value = {"forecast": SCHEDULE_UUID}
    mock_client.get_forecast.return_value = {"values": [2.0]}
    mock_client.get_asset_jobs.return_value = {"jobs": []}

    async with make_session() as session:
        sensors = await session.call_tool("list_sensors", {"asset_id": 4})
        sensor = await session.call_tool("get_sensor", {"sensor_id": 1})
        created = await session.call_tool(
            "create_sensor",
            {
                "name": "power",
                "unit": "kW",
                "event_resolution": "PT1H",
                "generic_asset_id": 4,
                "timezone": "Europe/Amsterdam",
                "attributes": {"kind": "power"},
            },
        )
        posted = await session.call_tool(
            "post_sensor_data",
            {
                "sensor_id": 2,
                "values": [1.0, 2.0],
                "start": "2026-07-13T00:00:00+02:00",
                "duration": "PT2H",
                "unit": "kW",
                "prior": "2026-07-12T12:00:00+02:00",
            },
        )
        data = await session.call_tool(
            "get_sensor_data",
            {
                "sensor_id": 2,
                "start": "2026-07-13T00:00:00+02:00",
                "duration": "PT2H",
                "unit": "kW",
                "resolution": "PT1H",
            },
        )
        forecast = await session.call_tool(
            "trigger_forecast",
            {
                "sensor_id": 2,
                "start": "2026-07-13T00:00:00+02:00",
                "duration": "P1D",
                "model": "TrainPredictPipeline",
                "config": {"x": 1},
                "prior": "2026-07-12T12:00:00+02:00",
            },
        )
        forecast_values = await session.call_tool(
            "get_forecast", {"sensor_id": 2, "forecast_id": SCHEDULE_UUID}
        )
        jobs = await session.call_tool("list_asset_jobs", {"asset_id": 4})

    assert sensors.structuredContent["result"] == [{"id": 1}]
    assert sensor.structuredContent == {"id": 1}
    assert created.structuredContent == {"id": 2}
    assert posted.structuredContent["n_values"] == 2
    assert data.structuredContent == {"values": [1.0]}
    assert forecast.structuredContent["forecast_id"] == SCHEDULE_UUID
    assert forecast_values.structuredContent == {"values": [2.0]}
    assert jobs.structuredContent == {"jobs": []}
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


async def test_create_automation_builds_optional_payload(make_session, mock_client):
    mock_client.add_automation.return_value = {"id": 2, "type": "schedules"}
    async with make_session() as session:
        result = await session.call_tool(
            "create_automation",
            {
                "asset_id": 5,
                "type": "schedules",
                "name": "daily schedule",
                "cronstr": "15 7 * * *",
                "parameters": {"duration": "PT24H"},
                "generator": "StorageScheduler",
                "config": {"queue": "scheduling"},
                "active": False,
            },
        )
    assert not result.isError
    payload = mock_client.add_automation.call_args.kwargs["automation"]
    assert payload == {
        "type": "schedules",
        "name": "daily schedule",
        "cronstr": "15 7 * * *",
        "parameters": {"duration": "PT24H"},
        "generator": "StorageScheduler",
        "config": {"queue": "scheduling"},
        "active": False,
    }


async def test_update_automation_sends_only_provided_fields(make_session, mock_client):
    mock_client.update_automation.return_value = {"id": 7, "active": False}
    async with make_session() as session:
        result = await session.call_tool(
            "update_automation",
            {
                "asset_id": 5,
                "automation_id": 7,
                "active": False,
            },
        )
    assert not result.isError
    assert mock_client.update_automation.call_args.kwargs["updates"] == {
        "active": False
    }


async def test_delete_tools_are_gated_and_call_client(make_session, mock_client):
    async with make_session(enable_delete=True) as session:
        asset_result = await session.call_tool("delete_asset", {"asset_id": 5})
        automation_result = await session.call_tool(
            "delete_automation", {"asset_id": 5, "automation_id": 7}
        )

    assert asset_result.structuredContent == {"deleted": True, "asset_id": 5}
    assert automation_result.structuredContent == {
        "deleted": True,
        "automation_id": 7,
    }
    mock_client.delete_asset.assert_awaited_once_with(
        asset_id=5, confirm_first=False
    )
    mock_client.delete_automation.assert_awaited_once_with(
        asset_id=5, automation_id=7
    )


async def test_authenticate_swaps_credentials(make_session, mock_client):
    mock_client.get_user.return_value = {"id": 3, "email": "new@example.com"}
    async with make_session(enable_auth_tool=True) as session:
        result = await session.call_tool(
            "authenticate",
            {"email": "new@example.com", "password": "new-secret"},
        )

    assert not result.isError
    assert result.structuredContent["authenticated"] is True
    assert mock_client.email == "new@example.com"
    assert mock_client.password == "new-secret"
    assert mock_client.access_token is None
    mock_client.get_access_token.assert_awaited_once()
