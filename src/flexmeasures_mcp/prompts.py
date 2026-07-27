"""MCP prompts: recipes for common FlexMeasures workflows."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from flexmeasures_mcp.config import Settings


def register(mcp: FastMCP, settings: Settings) -> None:
    if not settings.read_only:
        _register_write_prompts(mcp)

    @mcp.prompt()
    def diagnose_failed_job(job_id: str = "", asset_id: str = "") -> str:
        """Diagnose why a forecasting or scheduling job failed."""
        target = (
            f"job {job_id}"
            if job_id
            else f"the most recent failed job on asset {asset_id}"
        )
        if settings.read_only:
            final_step = """4. This server is read-only, so do not attempt fixes yourself: report the root cause and the exact recommended fix (data to post, flex-model change, or operational action) to the user."""
        else:
            final_step = """4. Apply the fix where it is data- or config-related, re-trigger, and confirm the new job finishes. Summarize root cause and what you changed."""
        return f"""Diagnose {target} in FlexMeasures:

1. If you only have an asset, call list_asset_jobs({asset_id or '<asset_id>'}) and pick the failed job.
2. Call get_job_status(job_id=...) and read status, message and exc_info.
3. Map the failure to a cause and fix:
   - infeasible flex-model (SoC targets unreachable, capacities too tight) -> relax constraints and re-trigger
   - missing price/forecast data in the planning window -> post or forecast the missing series first
   - unknown/inaccessible sensor in flex-context -> check IDs and account access with get_sensor
   - too little training data (forecasting) -> post more history
   - Redis/worker unavailable (503) -> the instance needs its workers running
{final_step}"""


def _register_write_prompts(mcp: FastMCP) -> None:
    @mcp.prompt()
    def build_site_and_run_schedule(
        site_name: str,
        timezone: str = "Europe/Amsterdam",
        battery_capacity_kwh: str = "900",
        battery_power_kw: str = "500",
    ) -> str:
        """Build a minimal FlexMeasures site with a battery and compute an
        optimized charging schedule against day-ahead prices."""
        return f"""Build a FlexMeasures site called "{site_name}" and compute a battery schedule. Follow these steps, verifying each before moving on:

1. Call health_check and connection_info to verify the connection and learn your account ID.
2. Call list_asset_types, then create_asset for the site (type "site" or similar) and a battery child asset (type "battery", parent_asset_id = the site's ID).
3. Call create_sensor for each required time series:
   - a power sensor on the battery (unit "kW" or "MW", event_resolution "PT15M")
   - a day-ahead price sensor (unit "EUR/MWh", event_resolution "PT1H") - put it on the site asset
4. Set the site's flex-context so the scheduler knows the prices: update_asset on the site with {{"flex_context": {{"consumption-price": {{"sensor": <price sensor ID>}}, "production-price": {{"sensor": <price sensor ID>}}}}}}.
5. Call post_sensor_data to post ~24h of hourly prices to the price sensor (start at the upcoming midnight in {timezone}, duration "PT24H").
6. If forecast inputs are needed for other sensors, call trigger_forecast and poll get_job_status until FINISHED.
7. Call trigger_schedule on the battery's power sensor (or the site asset) for the same 24h window, with a storage flex-model, e.g.:
   {{"soc-at-start": "0 kWh", "soc-min": "0 kWh", "soc-max": "{battery_capacity_kwh} kWh", "power-capacity": "{battery_power_kw} kW"}}
   (as a list of one dict with a "sensor" key if you target the asset).
8. Poll get_job_status(job_id=<schedule UUID>) until FINISHED (if FAILED, read exc_info, fix the flex-model or data, and re-trigger).
9. Call get_schedule(sensor_id=<battery power sensor>, schedule_id=<UUID>) to retrieve the schedule.
10. Summarize: created asset and sensor IDs, the data range posted, job UUIDs, and the schedule's start, duration and first values. Explain in one or two sentences why the schedule looks the way it does (e.g. charging in cheap hours)."""

    @mcp.prompt()
    def add_measurements_and_forecast(sensor_id: str, horizon_days: str = "2") -> str:
        """Post historical data to a sensor, then create and inspect a forecast."""
        return f"""For sensor {sensor_id} in FlexMeasures:

1. Call get_sensor({sensor_id}) to learn its unit and event resolution.
2. If it lacks recent history, post plausible historical values with post_sensor_data (at least a few weeks helps model training).
3. Call trigger_forecast(sensor_id={sensor_id}, start=<now, rounded to the sensor resolution>, duration="P{horizon_days}D").
4. Poll get_job_status(job_id=<forecast UUID>) until FINISHED (on FAILED, read exc_info - often there is too little training data).
5. Call get_forecast(sensor_id={sensor_id}, forecast_id=<UUID>); if it lists child job IDs, fetch each.
6. Compare forecast values against the recent measurements and summarize quality, ranges and any anomalies."""

    @mcp.prompt()
    def setup_report_automation(
        asset_id: str, goal_description: str, cronstr: str = "0 6 * * *"
    ) -> str:
        """Set up a recurring report on an asset (reports only run via cron automations)."""
        return f"""Set up a recurring report on FlexMeasures asset {asset_id}: {goal_description}

1. Call get_asset({asset_id}) and list_sensors(asset_id={asset_id}) to see the available input sensors; create an output sensor with create_sensor if none fits.
2. Draft PandasReporter parameters: input sensors (as "input" entries), the pandas method chain that computes the goal, and the output sensor(s).
3. Call create_report_automation(asset_id={asset_id}, name=<short name>, cronstr="{cronstr}", generator="PandasReporter", parameters=<drafted parameters>).
4. Verify with get_automation - check the recurrence description and that parameters were accepted.
5. Note to the user: there is no run-now endpoint for reports; the first results appear on the output sensor after the cron first fires. They can check with get_sensor_data on the output sensor, or adjust the schedule with update_automation."""
