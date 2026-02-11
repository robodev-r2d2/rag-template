"""Authorization and scope resolution for knowledge spaces."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rag_core_api.impl.settings.knowledge_space_settings import KnowledgeSpaceSettings
from rag_core_api.knowledge_spaces.models import KnowledgeSpace, KnowledgeSpaceType
from rag_core_lib.principal import Principal

logger = logging.getLogger(__name__)


class KnowledgeSpaceAccessDeniedError(PermissionError):
    """Raised when a caller requests an unauthorized knowledge space."""


class KnowledgeSpaceAccessService:
    """Resolves readable/writable knowledge spaces for a principal."""

    def __init__(self, settings: KnowledgeSpaceSettings):
        self._settings = settings
        self._state_file = Path(settings.knowledge_spaces_state_file) if settings.knowledge_spaces_state_file else None
        self._state_file_mtime_ns: int | None = None
        self._disabled_space_ids: set[str] = set()

    @staticmethod
    def _enabled_value(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _refresh_disabled_spaces(self) -> None:
        if self._state_file is None:
            self._disabled_space_ids = set()
            self._state_file_mtime_ns = None
            return
        try:
            if not self._state_file.exists():
                self._disabled_space_ids = set()
                self._state_file_mtime_ns = None
                return

            mtime_ns = self._state_file.stat().st_mtime_ns
            if self._state_file_mtime_ns == mtime_ns:
                return

            parsed = json.loads(self._state_file.read_text())
            raw_spaces = parsed.get("spaces", {}) if isinstance(parsed, dict) else {}
            spaces = raw_spaces if isinstance(raw_spaces, dict) else {}
            disabled: set[str] = set()
            for space_id, payload in spaces.items():
                if not isinstance(payload, dict):
                    continue
                if not self._enabled_value(payload.get("enabled", True)):
                    disabled.add(str(space_id))

            self._disabled_space_ids = disabled
            self._state_file_mtime_ns = mtime_ns
        except Exception:
            logger.exception("Failed loading knowledge-space state from '%s'.", self._state_file)

    def _filter_enabled_spaces(self, spaces: list[KnowledgeSpace]) -> list[KnowledgeSpace]:
        self._refresh_disabled_spaces()
        return [space for space in spaces if space.enabled and space.id not in self._disabled_space_ids]

    def tenant_space(self, tenant_id: str) -> KnowledgeSpace:
        """Build tenant-private knowledge space."""
        return KnowledgeSpace(
            id=self._settings.tenant_space_id(tenant_id),
            type=KnowledgeSpaceType.TENANT,
            tenant_id=tenant_id,
            display_name=f"Tenant {tenant_id}",
            enabled=True,
        )

    def shared_domain_space(self, domain_id: str) -> KnowledgeSpace:
        """Build domain-shared knowledge space."""
        return KnowledgeSpace(
            id=self._settings.shared_domain_space_id(domain_id),
            type=KnowledgeSpaceType.SHARED_DOMAIN,
            domain_id=domain_id,
            display_name=f"Shared ({domain_id})",
            enabled=True,
        )

    def global_space(self) -> KnowledgeSpace:
        """Build global knowledge space."""
        return KnowledgeSpace(
            id=self._settings.global_space_id(),
            type=KnowledgeSpaceType.GLOBAL,
            display_name="Global",
            enabled=True,
        )

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped

    def _tenant_ids_for_read(self, principal: Principal) -> list[str]:
        tenant_ids = self._dedupe([principal.tenant_id] + principal.allowed_tenant_ids)
        return [tenant_id for tenant_id in tenant_ids if tenant_id]

    def _domain_ids_for_read(self, principal: Principal) -> list[str]:
        return [domain_id for domain_id in self._dedupe(principal.allowed_domain_ids) if domain_id]

    def resolve_readable_spaces(self, principal: Principal | None) -> list[KnowledgeSpace]:
        """Resolve all spaces readable by the principal."""
        if principal is None or principal.is_anonymous:
            return self._filter_enabled_spaces([self.global_space()])

        spaces = [self.tenant_space(tenant_id) for tenant_id in self._tenant_ids_for_read(principal)]
        spaces.extend(self.shared_domain_space(domain_id) for domain_id in self._domain_ids_for_read(principal))
        spaces.append(self.global_space())
        return self._filter_enabled_spaces(spaces)

    def resolve_writable_spaces(self, principal: Principal | None) -> list[KnowledgeSpace]:
        """Resolve all spaces writable by the principal."""
        if principal is None or principal.is_anonymous:
            return []

        spaces: list[KnowledgeSpace] = []
        if principal.tenant_id:
            spaces.append(self.tenant_space(principal.tenant_id))
        if principal.can_write_shared_domain:
            spaces.extend(self.shared_domain_space(domain_id) for domain_id in self._domain_ids_for_read(principal))
        if principal.can_write_global:
            spaces.append(self.global_space())
        return self._filter_enabled_spaces(spaces)

    def _normalize_target_alias(self, principal: Principal | None, space_id: str | None) -> str | None:
        if space_id is None:
            return None
        normalized = space_id.strip()
        if not normalized:
            return None
        if normalized in {"tenant", "my_tenant"} and principal and principal.tenant_id:
            return self._settings.tenant_space_id(principal.tenant_id)
        if normalized == "global":
            return self._settings.global_space_id()
        return normalized

    def resolve_effective_scope(
        self, principal: Principal | None, requested_scope_ids: list[str] | None
    ) -> list[KnowledgeSpace]:
        """Resolve effective readable scope = requested scope ∩ readable scope."""
        readable_spaces = self.resolve_readable_spaces(principal)
        if not requested_scope_ids:
            return readable_spaces

        readable_map = {space.id: space for space in readable_spaces}
        normalized_requested = self._dedupe(
            [self._normalize_target_alias(principal, requested) for requested in requested_scope_ids]
        )
        normalized_requested = [requested for requested in normalized_requested if requested]
        if not normalized_requested:
            return readable_spaces

        disallowed = [requested for requested in normalized_requested if requested not in readable_map]
        if disallowed:
            raise KnowledgeSpaceAccessDeniedError(
                f"Requested scope {', '.join(disallowed)} is not readable for this principal."
            )
        return [readable_map[space_id] for space_id in normalized_requested]

    def resolve_upload_target(self, principal: Principal | None, target_space_id: str | None) -> KnowledgeSpace:
        """Resolve and authorize upload target; defaults to tenant space."""
        writable_spaces = self.resolve_writable_spaces(principal)
        if not writable_spaces:
            raise KnowledgeSpaceAccessDeniedError("No writable knowledge spaces available.")

        writable_map = {space.id: space for space in writable_spaces}
        normalized_target = self._normalize_target_alias(principal, target_space_id)

        if normalized_target:
            if normalized_target not in writable_map:
                raise KnowledgeSpaceAccessDeniedError(
                    f"Upload target {normalized_target} is not writable for this principal."
                )
            return writable_map[normalized_target]

        if principal and principal.tenant_id:
            default_tenant_space = self._settings.tenant_space_id(principal.tenant_id)
            if default_tenant_space in writable_map:
                return writable_map[default_tenant_space]

        return writable_spaces[0]

    def resolve_delete_scope(self, principal: Principal | None, target_space_id: str | None) -> list[KnowledgeSpace]:
        """Resolve writable delete scope; optional explicit target narrows scope."""
        writable_spaces = self.resolve_writable_spaces(principal)
        if not writable_spaces:
            raise KnowledgeSpaceAccessDeniedError("No writable knowledge spaces available.")

        normalized_target = self._normalize_target_alias(principal, target_space_id)
        if not normalized_target:
            return writable_spaces

        writable_map = {space.id: space for space in writable_spaces}
        if normalized_target not in writable_map:
            raise KnowledgeSpaceAccessDeniedError(
                f"Delete target {normalized_target} is not writable for this principal."
            )
        return [writable_map[normalized_target]]
