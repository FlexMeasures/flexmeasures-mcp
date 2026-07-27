from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration, read from environment variables.

    Connection settings use the FLEXMEASURES_ prefix (matching the naming
    that flexmeasures-client users know); MCP-server-specific toggles use
    the FLEXMEASURES_MCP_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLEXMEASURES_", extra="ignore", populate_by_name=True
    )

    host: str = "localhost:5000"
    ssl: bool | None = None  # None: infer from host (https unless localhost)
    email: str | None = None
    password: str | None = None
    access_token: str | None = None

    read_only: bool = Field(
        default=False,
        validation_alias=AliasChoices("FLEXMEASURES_MCP_READ_ONLY"),
    )
    enable_delete: bool = Field(
        default=False,
        validation_alias=AliasChoices("FLEXMEASURES_MCP_ENABLE_DELETE"),
    )
    enable_auth_tool: bool = Field(
        default=False,
        validation_alias=AliasChoices("FLEXMEASURES_MCP_ENABLE_AUTH_TOOL"),
    )

    @property
    def use_ssl(self) -> bool:
        if self.ssl is not None:
            return self.ssl
        return not self.host.split(":")[0] in ("localhost", "127.0.0.1")
