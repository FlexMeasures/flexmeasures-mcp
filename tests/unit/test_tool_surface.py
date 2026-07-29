"""The advertised tool/prompt/resource surface is stable and gated correctly."""

from __future__ import annotations

import json
import re

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

WRITE_TOOLS = {
    "create_asset",
    "update_asset",
    "create_sensor",
    "post_sensor_data",
    "trigger_forecast",
    "trigger_schedule",
    "create_automation",
    "create_report_automation",
    "update_automation",
}

# Read tools are named list_* / get_* after their OpenAPI operationIds; these
# two are the only reads that are not.
READ_ONLY_ALLOWED = {"health_check", "connection_info"}


async def test_default_tool_surface(make_session):
    async with make_session() as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS


async def test_gated_tools_appear_when_enabled(make_session):
    async with make_session(enable_delete=True, enable_auth_tool=True) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS | GATED_TOOLS


async def test_read_only_tool_surface(make_session):
    async with make_session(read_only=True) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS - WRITE_TOOLS


async def test_read_only_wins_over_gated_tools(make_session, caplog):
    async with make_session(
        read_only=True, enable_delete=True, enable_auth_tool=True
    ) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    assert tools == EXPECTED_TOOLS - WRITE_TOOLS
    assert "Read-only mode wins" in caplog.text


async def test_read_only_surface_is_only_reads(make_session):
    """No tool outside the documented read surface survives read-only mode.

    Convention-based on purpose. The WRITE_TOOLS tests above pin the exact
    surface, but they compare against a set maintained by hand: a new mutating
    tool that is registered with @mcp.tool() instead of @write_tool lands in
    EXPECTED_TOOLS and not in WRITE_TOOLS, so it appears on both sides of that
    comparison and passes. This one fails automatically instead.
    """
    async with make_session(read_only=True) as session:
        tools = {t.name for t in (await session.list_tools()).tools}
    offenders = sorted(
        t
        for t in tools
        if not (t.startswith(("list_", "get_")) or t in READ_ONLY_ALLOWED)
    )
    assert not offenders, f"non-read tools in read-only mode: {offenders}"


async def test_read_only_prompt_surface(make_session):
    """Write-workflow prompts are hidden; diagnosis stays, resources stay."""
    async with make_session(read_only=True) as session:
        prompts = {p.name for p in (await session.list_prompts()).prompts}
        resources = {str(r.uri) for r in (await session.list_resources()).resources}
        prompt = await session.get_prompt("diagnose_failed_job", {"job_id": "job-123"})
    assert prompts == {"diagnose_failed_job"}
    assert "flexmeasures://docs/flex-model" in resources
    assert "flexmeasures://docs/flex-context" in resources
    assert "read-only" in prompt.messages[0].content.text


async def test_read_only_prompt_calls_only_available_tools(make_session):
    """A prompt must not point the agent at a tool this mode does not serve."""
    async with make_session(read_only=True) as session:
        available = {t.name for t in (await session.list_tools()).tools}
        prompt = await session.get_prompt("diagnose_failed_job", {"job_id": "j"})
    called = set(re.findall(r"\b([a-z][a-z_]{2,})\(", prompt.messages[0].content.text))
    assert not called - available, f"unavailable tools: {sorted(called - available)}"


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
