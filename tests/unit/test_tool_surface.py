"""The advertised tool/prompt/resource surface is stable and gated correctly."""

from __future__ import annotations

import json

from flexmeasures_mcp import server as server_module

EXPECTED_TOOLS = {
    "health_check",
    "connection_info",
    "list_asset_types",
    "list_assets",
    "get_asset",
    "create_asset",
    "update_asset",
    "list_sensors",
    "get_sensor",
    "create_sensor",
    "post_sensor_data",
    "get_sensor_data",
    "trigger_forecast",
    "get_forecast",
    "trigger_schedule",
    "get_schedule",
    "get_job_status",
    "list_asset_jobs",
    "create_automation",
    "create_report_automation",
    "list_automations",
    "get_automation",
    "update_automation",
}

GATED_TOOLS = {"delete_asset", "delete_automation", "authenticate"}


async def test_default_tool_surface(make_session):
    async with make_session() as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS


async def test_gated_tools_appear_when_enabled(make_session):
    async with make_session(enable_delete=True, enable_auth_tool=True) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS | GATED_TOOLS


async def test_prompts_and_resources(make_session):
    async with make_session() as session:
        prompts = {p.name for p in (await session.list_prompts()).prompts}
        resources = {str(r.uri) for r in (await session.list_resources()).resources}
    assert prompts == {
        "build_site_and_run_schedule",
        "add_measurements_and_forecast",
        "setup_report_automation",
        "diagnose_failed_job",
    }
    assert "flexmeasures://docs/flex-model" in resources
    assert "flexmeasures://docs/flex-context" in resources


async def test_prompt_rendering_and_openapi_resource(make_session):
    async with make_session(ssl=True) as session:
        prompt = await session.get_prompt(
            "diagnose_failed_job", {"job_id": "job-123"}
        )
        resource = await session.read_resource("flexmeasures://server/openapi-url")

    assert "job job-123" in prompt.messages[0].content.text
    assert (
        "https://test-host/ui/static/openapi-specs.json"
        in resource.contents[0].text
    )


async def test_plugin_entry_points_are_loaded_and_isolated(
    make_session, monkeypatch, caplog
):
    class EntryPoint:
        def __init__(self, name, loader):
            self.name = name
            self._loader = loader

        def load(self):
            return self._loader

    def good_plugin(mcp, _settings):
        @mcp.tool()
        async def plugin_echo() -> dict:
            return {"plugin": True}

    def bad_plugin(_mcp, _settings):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        server_module,
        "entry_points",
        lambda group: [
            EntryPoint("good", good_plugin),
            EntryPoint("bad", bad_plugin),
        ],
    )

    async with make_session() as session:
        tools = {t.name for t in (await session.list_tools()).tools}
        result = await session.call_tool("plugin_echo", {})

    assert "plugin_echo" in tools
    assert json.loads(result.content[0].text) == {"plugin": True}
    assert "Failed to load flexmeasures_mcp.tools plugin bad" in caplog.text
