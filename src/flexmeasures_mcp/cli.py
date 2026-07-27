"""Console entry point."""

from __future__ import annotations

import argparse
import logging

from flexmeasures_mcp.config import Settings
from flexmeasures_mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="flexmeasures-mcp",
        description=(
            "MCP server for FlexMeasures. Connection settings come from "
            "environment variables (FLEXMEASURES_HOST, FLEXMEASURES_EMAIL, "
            "FLEXMEASURES_PASSWORD or FLEXMEASURES_ACCESS_TOKEN, "
            "FLEXMEASURES_SSL)."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport to serve on (default: stdio, for local MCP clients)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address for streamable-http"
    )
    parser.add_argument(
        "--port", type=int, default=8100, help="Port for streamable-http"
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help=(
            "Serve only inspection tools; hide every tool that creates, "
            "changes or triggers anything (same as FLEXMEASURES_MCP_READ_ONLY=true)"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    mcp = create_server(Settings(read_only=True)) if args.read_only else create_server()
    if args.transport == "streamable-http":
        # Note: HTTP mode is single-identity - every caller acts as the
        # configured FlexMeasures user. Do not expose it publicly without
        # an authenticating proxy in front.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
