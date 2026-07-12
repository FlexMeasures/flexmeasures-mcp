from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from flexmeasures_mcp.client import ExtendedFlexMeasuresClient
from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.server import create_server


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=ExtendedFlexMeasuresClient)
    client.host = "test-host"
    return client


@pytest.fixture
def make_session(mock_client):
    """Yield an in-process MCP client session talking to a server whose
    FlexMeasures client is mocked."""

    @asynccontextmanager
    async def _make(**settings_kwargs):
        settings = Settings(
            host="test-host", email="test@seita.nl", password="secret", **settings_kwargs
        )
        server = create_server(settings=settings, client_factory=lambda _s: mock_client)
        async with create_connected_server_and_client_session(
            server._mcp_server
        ) as session:
            yield session

    return _make
