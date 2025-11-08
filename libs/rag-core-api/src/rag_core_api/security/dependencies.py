"""FastAPI dependencies for security and access control."""

from __future__ import annotations

import functools
import logging

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rag_core_api.impl.settings.keycloak_settings import KeycloakSettings
from rag_core_api.security.keycloak import KeycloakAuthenticator
from rag_core_api.security.models import UserContext
from rag_core_lib.impl.settings.access_control_settings import AccessControlSettings

logger = logging.getLogger(__name__)


bearer_scheme = HTTPBearer(auto_error=False)


@functools.lru_cache(maxsize=1)
def _authenticator() -> KeycloakAuthenticator:
    settings = KeycloakSettings()
    access_settings = AccessControlSettings()
    return KeycloakAuthenticator(settings=settings, access_control_settings=access_settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> UserContext:
    """Return the current user as determined by the Authorization header."""

    authenticator = _authenticator()
    settings = KeycloakSettings()
    if credentials is None:
        if settings.enforce:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
        logger.debug("No credentials supplied and enforcement disabled; returning anonymous user")
        return UserContext(subject="anonymous", groups={AccessControlSettings().public_group})

    return await authenticator.authenticate(credentials.credentials)


async def require_admin_user(user: UserContext = Depends(get_current_user)) -> UserContext:
    """Ensure the current user has administrative privileges."""

    settings = KeycloakSettings()
    access_settings = AccessControlSettings()
    if not user.has_role(settings.admin_role, access_settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
