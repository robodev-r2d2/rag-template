"""Settings for knowledge spaces and multitenancy collection strategy."""

from __future__ import annotations

from string import Formatter
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            fields.add(field_name)
    return fields


class KnowledgeSpaceSettings(BaseSettings):
    """Configuration for logical knowledge spaces and physical collection mapping."""

    model_config = SettingsConfigDict(case_sensitive=False, populate_by_name=True)

    collection_strategy: Literal["single", "hybrid", "isolated"] = Field(
        default="single", validation_alias="MULTITENANCY_COLLECTION_STRATEGY"
    )
    tenant_collection_template: str = Field(
        default="tenant_{tenant_id}", validation_alias="MULTITENANCY_TENANT_COLLECTION_TEMPLATE"
    )
    shared_domain_collection_template: str = Field(
        default="shared_{domain_id}", validation_alias="MULTITENANCY_SHARED_DOMAIN_COLLECTION_TEMPLATE"
    )
    global_collection_name: str = Field(
        default="shared_global", validation_alias="MULTITENANCY_GLOBAL_COLLECTION_NAME"
    )
    knowledge_spaces_state_file: str = Field(
        default="infrastructure/rag/knowledge-spaces-state.json",
        validation_alias="KNOWLEDGE_SPACES_STATE_FILE",
    )
    enable_space_selector_in_chat: bool = Field(
        default=False, validation_alias="ENABLE_SPACE_SELECTOR_IN_CHAT"
    )
    enable_upload_sharing_target: bool = Field(
        default=False, validation_alias="ENABLE_UPLOAD_SHARING_TARGET"
    )
    allow_anonymous_chat: bool = Field(default=False, validation_alias="ALLOW_ANONYMOUS_CHAT")

    @field_validator("tenant_collection_template")
    @classmethod
    def _validate_tenant_template(cls, template: str) -> str:
        fields = _template_fields(template)
        if fields != {"tenant_id"}:
            raise ValueError("MULTITENANCY_TENANT_COLLECTION_TEMPLATE must contain only {tenant_id}.")
        return template

    @field_validator("shared_domain_collection_template")
    @classmethod
    def _validate_shared_template(cls, template: str) -> str:
        fields = _template_fields(template)
        if fields != {"domain_id"}:
            raise ValueError("MULTITENANCY_SHARED_DOMAIN_COLLECTION_TEMPLATE must contain only {domain_id}.")
        return template

    @field_validator("global_collection_name")
    @classmethod
    def _validate_global_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("MULTITENANCY_GLOBAL_COLLECTION_NAME must not be empty.")
        if "{" in value or "}" in value:
            raise ValueError("MULTITENANCY_GLOBAL_COLLECTION_NAME must not contain template placeholders.")
        return value

    @staticmethod
    def tenant_space_id(tenant_id: str) -> str:
        """Build tenant space id from tenant id."""
        return f"tenant_{tenant_id}"

    @staticmethod
    def shared_domain_space_id(domain_id: str) -> str:
        """Build shared-domain space id from domain id."""
        return f"shared_{domain_id}"

    @staticmethod
    def global_space_id() -> str:
        """Return global space id."""
        return "shared_global"
