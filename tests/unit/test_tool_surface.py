"""The advertised tool/prompt/resource surface is stable and gated correctly."""

from __future__ import annotations

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
