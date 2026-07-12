"""MCP resources: reference material for building flex-models and contexts."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from flexmeasures_mcp.config import Settings

FLEX_MODEL_DOC = """# FlexMeasures storage flex-model cheat sheet

The flex-model describes one flexible device in a scheduling request.
Quantities are strings with units ("0.5 MW", "20 kWh") or sensor references
({"sensor": <id>}). When triggering on an asset, pass a list of flex-models,
each with a "sensor" key naming the device's power sensor.

Common fields (storage devices such as batteries and EVs):
- soc-at-start: state of charge at the schedule start, e.g. "0.2 MWh"
- soc-min / soc-max: hard SoC bounds
- soc-minima / soc-maxima: time-based soft SoC constraints,
  e.g. [{"value": "0.5 MWh", "datetime": "2026-07-13T08:00:00+02:00"}]
- soc-targets: SoC values to reach at given datetimes (same shape as above)
- power-capacity: max power of the device (both directions)
- consumption-capacity / production-capacity: directional power limits
- charging-efficiency / discharging-efficiency: e.g. "95%" (or a COP value)
- storage-efficiency: retention per step, e.g. "99.7%"
- roundtrip-efficiency: alternative to the two directional efficiencies
- soc-unit: unit for bare-number SoC fields ("kWh" or "MWh")

Full reference:
https://flexmeasures.readthedocs.io/latest/features/scheduling.html
"""

FLEX_CONTEXT_DOC = """# FlexMeasures flex-context cheat sheet

The flex-context describes the site-level conditions shared by all devices.
It can be stored on the (site) asset - then scheduling requests can omit it -
or passed with trigger_schedule.

Common fields:
- consumption-price / production-price: price sensor refs, e.g. {"sensor": 9},
  or fixed quantities like "0.3 EUR/kWh"
- inflexible-device-sensors: power sensors of loads that just happen, e.g. [13, 14]
- site-power-capacity: grid connection size, e.g. "100 kVA"
- site-consumption-capacity / site-production-capacity: directional limits
- site-consumption-breach-price / site-production-breach-price: soft-constraint
  penalty prices, e.g. "1000 EUR/kW"
- site-peak-consumption / site-peak-production (+ their ...-price fields):
  peak shaving configuration

Full reference:
https://flexmeasures.readthedocs.io/latest/features/scheduling.html
"""


def register(mcp: FastMCP, settings: Settings) -> None:
    @mcp.resource("flexmeasures://docs/flex-model")
    def flex_model_doc() -> str:
        """Cheat sheet for describing device flexibility (flex-model)."""
        return FLEX_MODEL_DOC

    @mcp.resource("flexmeasures://docs/flex-context")
    def flex_context_doc() -> str:
        """Cheat sheet for describing site-level context (flex-context)."""
        return FLEX_CONTEXT_DOC

    @mcp.resource("flexmeasures://server/openapi-url")
    def openapi_url() -> str:
        """Where to find this instance's machine-readable OpenAPI spec."""
        scheme = "https" if settings.use_ssl else "http"
        return (
            f"{scheme}://{settings.host}/ui/static/openapi-specs.json\n"
            "Operations marked with x-mcp-tool form the curated tool surface; "
            "their operationIds match this server's tool names."
        )
