"""The full story: build a site, post data, schedule, and retrieve results.

Requires a live FlexMeasures stack with workers (see conftest.py).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from .conftest import requires_live_server

pytestmark = [pytest.mark.e2e, requires_live_server]

POLL_SECONDS = 2
POLL_ATTEMPTS = 60


async def _poll_job(session, job_id: str) -> dict:
    for _ in range(POLL_ATTEMPTS):
        result = await session.call_tool("get_job_status", {"job_id": job_id})
        assert not result.isError, result.content
        status = result.structuredContent["status"]
        if status in ("FINISHED", "FAILED"):
            return result.structuredContent
        await asyncio.sleep(POLL_SECONDS)
    pytest.fail(f"Job {job_id} did not finish in time")


async def test_build_site_and_run_schedule(live_session):
    run_id = uuid.uuid4().hex[:8]
    async with live_session() as session:
        # health + identity
        health = await session.call_tool("health_check", {})
        assert not health.isError, health.content
        info = await session.call_tool("connection_info", {})
        assert not info.isError

        # asset types -> site + battery
        types = (await session.call_tool("list_asset_types", {})).structuredContent[
            "result"
        ]
        type_by_name = {t["name"]: t["id"] for t in types}
        site_type = type_by_name.get("site", next(iter(type_by_name.values())))
        battery_type = type_by_name.get("battery", site_type)

        site = (
            await session.call_tool(
                "create_asset",
                {"name": f"e2e site {run_id}", "generic_asset_type_id": site_type},
            )
        ).structuredContent
        battery = (
            await session.call_tool(
                "create_asset",
                {
                    "name": f"e2e battery {run_id}",
                    "generic_asset_type_id": battery_type,
                    "parent_asset_id": site["id"],
                },
            )
        ).structuredContent

        # sensors
        power = (
            await session.call_tool(
                "create_sensor",
                {
                    "name": "power",
                    "unit": "kW",
                    "event_resolution": "PT1H",
                    "generic_asset_id": battery["id"],
                },
            )
        ).structuredContent
        price = (
            await session.call_tool(
                "create_sensor",
                {
                    "name": "price",
                    "unit": "EUR/MWh",
                    "event_resolution": "PT1H",
                    "generic_asset_id": site["id"],
                },
            )
        ).structuredContent

        # price data for tomorrow
        import pandas as pd

        start = (pd.Timestamp.utcnow().floor("D") + pd.Timedelta(days=1)).isoformat()
        prices = [50 + 30 * ((h % 24) in (8, 9, 18, 19)) for h in range(24)]
        posted = await session.call_tool(
            "post_sensor_data",
            {
                "sensor_id": price["id"],
                "values": prices,
                "start": start,
                "duration": "PT24H",
                "unit": "EUR/MWh",
            },
        )
        assert not posted.isError, posted.content

        # schedule the battery against those prices
        trigger = await session.call_tool(
            "trigger_schedule",
            {
                "sensor_id": power["id"],
                "start": start,
                "duration": "PT24H",
                "flex_model": {
                    "soc-at-start": "0 kWh",
                    "soc-min": "0 kWh",
                    "soc-max": "900 kWh",
                    "power-capacity": "500 kW",
                },
                "flex_context": {
                    "consumption-price": {"sensor": price["id"]},
                    "production-price": {"sensor": price["id"]},
                },
            },
        )
        assert not trigger.isError, trigger.content
        schedule_id = trigger.structuredContent["schedule_id"]

        job = await _poll_job(session, schedule_id)
        assert job["status"] == "FINISHED", job

        schedule = await session.call_tool(
            "get_schedule", {"sensor_id": power["id"], "schedule_id": schedule_id}
        )
        assert not schedule.isError, schedule.content
        values = schedule.structuredContent["values"]
        assert len(values) > 0


async def test_error_cases(live_session):
    async with live_session() as session:
        # nonexistent sensor
        missing = await session.call_tool("get_sensor", {"sensor_id": 999999})
        assert missing.isError

        # invalid flex-model field -> validation error surfaced, not a crash
        bad = await session.call_tool(
            "trigger_schedule",
            {
                "sensor_id": 999999,
                "start": "2026-07-13T00:00:00+02:00",
                "duration": "PT24H",
                "flex_model": {"soc-minn": 3},
            },
        )
        assert bad.isError
