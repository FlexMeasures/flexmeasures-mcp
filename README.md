# flexmeasures-mcp

mcp-name: io.github.flexmeasures/flexmeasures

An [MCP](https://modelcontextprotocol.io) server for [FlexMeasures](https://flexmeasures.io),
the open-source energy flexibility platform. It lets AI agents build and operate
complete sites: create assets and sensors, post time-series data, trigger
forecasting and scheduling jobs, poll job status, retrieve results, and manage
report automations — all through the FlexMeasures REST API, so the server's
authentication and permission model stays authoritative.

## Install

```sh
uvx flexmeasures-mcp          # run directly
# or
pipx install flexmeasures-mcp
```

Requires Python 3.10+ and a FlexMeasures instance (yours, or a hosted one).

## Configuration

| Environment variable | Required | Meaning |
|---|---|---|
| `FLEXMEASURES_HOST` | yes | Host (no scheme), e.g. `company.flexmeasures.io` or `localhost:5000` |
| `FLEXMEASURES_EMAIL` | yes* | User email to authenticate with |
| `FLEXMEASURES_PASSWORD` | yes* | User password (kept out of the agent's context) |
| `FLEXMEASURES_ACCESS_TOKEN` | no | Alternative to email/password; note tokens expire and cannot auto-refresh |
| `FLEXMEASURES_SSL` | no | `true`/`false`; default: `true` unless host is localhost |
| `FLEXMEASURES_MCP_ENABLE_DELETE` | no | Expose `delete_asset` / `delete_automation` tools (default off) |
| `FLEXMEASURES_MCP_ENABLE_AUTH_TOOL` | no | Expose an `authenticate(email, password)` tool (default off — credentials passed through it end up in the conversation transcript) |

\* either email+password or an access token.

### Claude Desktop

```json
{
  "mcpServers": {
    "flexmeasures": {
      "command": "uvx",
      "args": ["flexmeasures-mcp"],
      "env": {
        "FLEXMEASURES_HOST": "company.flexmeasures.io",
        "FLEXMEASURES_EMAIL": "me@company.com",
        "FLEXMEASURES_PASSWORD": "..."
      }
    }
  }
}
```

### Claude Code

```sh
claude mcp add flexmeasures \
  -e FLEXMEASURES_HOST=company.flexmeasures.io \
  -e FLEXMEASURES_EMAIL=me@company.com \
  -e FLEXMEASURES_PASSWORD=... \
  -- uvx flexmeasures-mcp
```

### HTTP mode (remote)

```sh
flexmeasures-mcp --transport streamable-http --host 0.0.0.0 --port 8100
```

⚠️ HTTP mode is **single-identity**: every connected client acts as the
configured FlexMeasures user. Put an authenticating proxy in front before
exposing it beyond localhost.

## Tools

Meta: `health_check`, `connection_info` (+ gated `authenticate`).
Assets: `list_asset_types`, `list_assets`, `get_asset`, `create_asset`, `update_asset` (+ gated `delete_asset`).
Sensors & data: `list_sensors`, `get_sensor`, `create_sensor`, `post_sensor_data`, `get_sensor_data`.
Jobs: `trigger_forecast`, `get_forecast`, `trigger_schedule`, `get_schedule`, `get_job_status`, `list_asset_jobs`.
Automations: `create_automation`, `create_report_automation`, `list_automations`, `get_automation`, `update_automation` (+ gated `delete_automation`).

Tool names match the stable `operationId`s in the FlexMeasures OpenAPI spec
(served by every instance at `/ui/static/openapi-specs.json`; the curated
surface is marked with `x-mcp-tool`).

Async semantics: `trigger_*` tools return a job UUID immediately (the API
responds 202); poll `get_job_status` until `FINISHED`, then fetch results with
`get_schedule` / `get_forecast`. Older FlexMeasures servers (< v3.0-32 API)
are also supported.

## Walkthrough: build and run a site

Use the bundled `build_site_and_run_schedule` prompt, or ask your agent:

> Build a FlexMeasures site "Demo plant" with a 900 kWh / 500 kW battery,
> post tomorrow's day-ahead prices, and compute an optimized charging
> schedule.

A typical run: `create_asset` (site, then battery with `parent_asset_id`) →
`create_sensor` (battery power in kW at PT15M; prices in EUR/MWh at PT1H) →
`update_asset` to point the site's flex-context at the price sensor →
`post_sensor_data` (24 hourly prices) → `trigger_schedule` with a storage
flex-model (`soc-at-start`, `soc-min`/`soc-max`, `power-capacity`) →
`get_job_status` until `FINISHED` → `get_schedule` → the agent summarizes IDs,
data ranges, job UUIDs and the schedule.

## Reports

Reports run only as **cron automations** in FlexMeasures — there is no run-now
endpoint. `create_report_automation` sets one up (e.g. with `PandasReporter`);
results appear on the report's output sensor(s) after the cron fires, readable
via `get_sensor_data`. Requires a FlexMeasures server with automations support.

## Extending

Third-party packages can add tools by declaring an entry point:

```toml
[project.entry-points."flexmeasures_mcp.tools"]
my_plugin = "my_pkg.mcp_tools:register"   # register(mcp: FastMCP, settings) -> None
```

Broken plugins are logged and skipped; they never prevent server startup.

## Development

```sh
uv venv && uv pip install -e ".[test]"
uv run pytest                 # unit tests (no server needed)
uv run pytest -m e2e          # end-to-end (see tests/e2e/conftest.py)
```

E2e tests need a live FlexMeasures stack with workers — use
`tests/e2e/docker-compose.yml` (own Postgres + Redis), never a shared instance.

## License

Apache 2.0
