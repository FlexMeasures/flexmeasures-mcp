"""End-to-end fixtures: run against a live FlexMeasures stack.

Bring up a stack with tests/e2e/docker-compose.yml (or point at a dev server
you own - NEVER a shared/production instance: these tests create assets and
enqueue jobs). Configure via environment variables:

    FLEXMEASURES_E2E_HOST=localhost:5000
    FLEXMEASURES_E2E_EMAIL=admin@seita.nl
    FLEXMEASURES_E2E_PASSWORD=...

Run with: pytest -m e2e
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.server import create_server

E2E_HOST = os.environ.get("FLEXMEASURES_E2E_HOST")
HEALTH_ATTEMPTS = int(os.environ.get("FLEXMEASURES_E2E_HEALTH_ATTEMPTS", "30"))
HEALTH_SECONDS = float(os.environ.get("FLEXMEASURES_E2E_HEALTH_SECONDS", "2"))


async def _wait_for_health(session):
    last_error = None
    for _ in range(HEALTH_ATTEMPTS):
        try:
            result = await session.call_tool("health_check", {})
        except Exception as exc:  # noqa: BLE001 - startup can fail in several layers
            last_error = exc
        else:
            if not result.isError:
                return
            last_error = result.content
        await asyncio.sleep(HEALTH_SECONDS)
    pytest.fail(f"FlexMeasures e2e server did not become healthy: {last_error}")


@pytest.fixture
def live_session():
    @asynccontextmanager
    async def _make(**settings_kwargs):
        settings = Settings(
            host=E2E_HOST,
            ssl=False,
            email=os.environ["FLEXMEASURES_E2E_EMAIL"],
            password=os.environ["FLEXMEASURES_E2E_PASSWORD"],
            **settings_kwargs,
        )
        server = create_server(settings=settings)
        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as session:
            await _wait_for_health(session)
            yield session

    return _make
