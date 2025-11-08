"""Settings module for access control configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AccessControlSettings(BaseSettings):
    """Settings that describe how document access control is handled."""

    class Config:
        """Configure environment variable prefix and behaviour."""

        env_prefix = "ACCESS_CONTROL_"
        case_sensitive = False

    metadata_key: str = Field(
        default="access_groups",
        description="Metadata key that stores allowed access groups on vector documents.",
    )
    default_group: str = Field(
        default="public",
        description="Fallback group applied when no explicit access control is defined.",
    )
    public_group: str = Field(
        default="public",
        description="Group that represents anonymous/public access.",
    )
    role_prefix: str = Field(
        default="role:",
        description="Prefix added when mapping user roles to access groups.",
    )
