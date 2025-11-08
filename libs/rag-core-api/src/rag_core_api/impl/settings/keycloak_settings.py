"""Settings for Keycloak based authentication."""

from pydantic import Field
from pydantic_settings import BaseSettings


class KeycloakSettings(BaseSettings):
    """Configuration required to talk to Keycloak."""

    class Config:
        """Pydantic configuration."""

        env_prefix = "KEYCLOAK_"
        case_sensitive = False

    enabled: bool = Field(default=True, description="Enable Keycloak authentication.")
    server_url: str = Field(
        default="http://rag-keycloak:8080",
        description="Base URL of the Keycloak server, e.g. https://keycloak.example.com",
    )
    realm: str = Field(default="rag", description="Realm that issues tokens.")
    introspection_client_id: str = Field(
        default="rag-backend",
        description="Client id that is allowed to call the introspection endpoint.",
    )
    introspection_client_secret: str = Field(
        default="rag-backend-secret",
        description="Client secret used for token introspection.",
    )
    resource_client_id: str = Field(
        default="rag-backend",
        description="Client id whose roles should be mapped to access groups.",
    )
    expected_audience: str | None = Field(
        default=None,
        description="If set, only tokens containing this audience are accepted.",
    )
    groups_claim: str = Field(default="groups", description="Claim that contains Keycloak groups.")
    admin_role: str = Field(default="rag-admin", description="Role that is allowed to perform admin actions.")
    enforce: bool = Field(default=True, description="Reject unauthenticated requests when True.")
    timeout_seconds: float = Field(default=5.0, description="Timeout for Keycloak HTTP calls.")

    @property
    def issuer(self) -> str:
        """Return the issuer URL for the configured realm."""

        return f"{self.server_url.rstrip('/')}/realms/{self.realm}"

    @property
    def introspection_url(self) -> str:
        """Return the token introspection endpoint URL."""

        return f"{self.issuer}/protocol/openid-connect/token/introspect"
