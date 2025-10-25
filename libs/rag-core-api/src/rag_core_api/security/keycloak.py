"""Keycloak authentication utilities."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

import requests
from fastapi import HTTPException, status

from rag_core_api.impl.settings.keycloak_settings import KeycloakSettings
from rag_core_api.security.models import UserContext
from rag_core_lib.impl.settings.access_control_settings import AccessControlSettings

logger = logging.getLogger(__name__)


class KeycloakAuthenticator:
    """Authenticate and authorise users via Keycloak introspection."""

    def __init__(
        self,
        settings: KeycloakSettings,
        access_control_settings: AccessControlSettings,
    ):
        self._settings = settings
        self._access_settings = access_control_settings
        self._session = requests.Session()
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def authenticate(self, token: str) -> UserContext:
        """Validate the provided token and return a :class:`UserContext`."""

        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

        if not self._settings.enabled:
            logger.debug("Keycloak authentication disabled, returning anonymous context")
            return UserContext(subject="anonymous", groups={self._access_settings.public_group})

        data = await asyncio.to_thread(self._introspect_token, token)

        if not data.get("active", False):
            logger.info("Inactive token received from Keycloak introspection")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive access token")

        audience = data.get("aud")
        if self._settings.expected_audience and not self._audience_matches(audience):
            logger.warning("Token rejected because expected audience %s was not present", self._settings.expected_audience)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid audience")

        subject = str(data.get("sub") or data.get("username") or data.get("preferred_username") or "user")
        username = data.get("username") or data.get("preferred_username")
        email = data.get("email")
        roles = set(self._extract_roles(data))
        groups = set(self._extract_groups(data))

        context = UserContext(subject=subject, username=username, email=email, roles=roles, groups=groups)
        logger.debug("Authenticated user %s with roles %s and groups %s", subject, roles, groups)
        return context

    def _audience_matches(self, audience: Any) -> bool:
        """Return True if the configured audience is present in the token."""

        if audience is None:
            return False
        if isinstance(audience, (list, tuple, set)):
            return self._settings.expected_audience in audience
        return str(audience) == str(self._settings.expected_audience)

    def _introspect_token(self, token: str) -> Dict[str, Any]:
        """Call Keycloak's introspection endpoint and cache the result."""

        now = time.time()
        cached = self._cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

        response = self._session.post(
            self._settings.introspection_url,
            data={"token": token, "token_type_hint": "access_token"},
            auth=(self._settings.introspection_client_id, self._settings.introspection_client_secret),
            timeout=self._settings.timeout_seconds,
        )

        if response.status_code != status.HTTP_200_OK:
            logger.error("Keycloak introspection failed with status %s", response.status_code)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token introspection failed")

        data = response.json()
        ttl = float(data.get("exp", now + 30)) - now
        expires_at = now + max(ttl, 30)
        self._cache[token] = (expires_at, data)
        return data

    def _extract_roles(self, data: dict[str, Any]) -> set[str]:
        roles = set()
        realm_access = data.get("realm_access") or {}
        roles.update(realm_access.get("roles", []) or [])

        resource_access = data.get("resource_access") or {}
        client_roles = resource_access.get(self._settings.resource_client_id) or {}
        roles.update(client_roles.get("roles", []) or [])
        return {str(role) for role in roles if role}

    def _extract_groups(self, data: dict[str, Any]) -> set[str]:
        groups = data.get(self._settings.groups_claim, [])
        if isinstance(groups, str):
            groups = [groups]
        try:
            return {str(group) for group in groups if group}
        except TypeError:
            return set()
