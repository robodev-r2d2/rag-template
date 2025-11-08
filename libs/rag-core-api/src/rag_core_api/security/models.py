"""Security related domain models."""

from dataclasses import dataclass, field
from typing import Iterable, Set

from rag_core_lib.impl.settings.access_control_settings import AccessControlSettings


@dataclass(frozen=True)
class UserContext:
    """Represents the authenticated user."""

    subject: str
    username: str | None = None
    email: str | None = None
    roles: Set[str] = field(default_factory=set)
    groups: Set[str] = field(default_factory=set)

    def with_additional_groups(self, groups: Iterable[str]) -> "UserContext":
        """Return a copy of the context extended with additional groups."""

        return UserContext(
            subject=self.subject,
            username=self.username,
            email=self.email,
            roles=set(self.roles),
            groups=set(self.groups) | set(groups),
        )

    def allowed_groups(self, settings: AccessControlSettings) -> Set[str]:
        """Return groups that should be used for metadata filtering."""

        allowed = set(self.groups)
        allowed.add(settings.default_group)
        allowed.add(settings.public_group)
        allowed |= {f"{settings.role_prefix}{role}" for role in self.roles}
        return {group for group in allowed if group}

    def has_role(self, role: str, settings: AccessControlSettings | None = None) -> bool:
        """Return ``True`` if the user owns the given role."""

        if role in self.roles:
            return True
        if settings:
            prefixed = f"{settings.role_prefix}{role}" if role and not role.startswith(settings.role_prefix) else role
            return prefixed in self.groups
        return False
