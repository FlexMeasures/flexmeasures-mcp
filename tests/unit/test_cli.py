"""Command-line entry point behavior."""

from __future__ import annotations

from types import SimpleNamespace

from flexmeasures_mcp import cli


class FakeServer:
    def __init__(self):
        self.settings = SimpleNamespace(host=None, port=None)
        self.runs = []

    def run(self, **kwargs):
        self.runs.append(kwargs)


def test_cli_defaults_to_stdio(monkeypatch):
    fake = FakeServer()
    monkeypatch.setattr(cli, "create_server", lambda: fake)
    monkeypatch.setattr("sys.argv", ["flexmeasures-mcp"])

    cli.main()

    assert fake.runs == [{"transport": "stdio"}]


def test_cli_configures_streamable_http(monkeypatch):
    fake = FakeServer()
    monkeypatch.setattr(cli, "create_server", lambda: fake)
    monkeypatch.setattr(
        "sys.argv",
        [
            "flexmeasures-mcp",
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ],
    )

    cli.main()

    assert fake.settings.host == "0.0.0.0"
    assert fake.settings.port == 9000
    assert fake.runs == [{"transport": "streamable-http"}]
