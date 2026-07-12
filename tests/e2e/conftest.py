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

import os
from contextlib import asynccontextmanager

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.server import create_server

E2E_HOST = os.environ.get("FLEXMEASURES_E2E_HOST")


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
            yield session

    return _make
