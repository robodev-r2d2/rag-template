"""Module for authentication middleware."""

import logging
import json
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import InvalidSignatureError
import requests
from keycloak import KeycloakOpenID
from rag_core_lib.context import set_tenant_id
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class KeycloakSettings(BaseSettings):
    """Keycloak settings."""

    KEYCLOAK_SERVER_URL: str = "http://localhost:8080/"
    KEYCLOAK_REALM_NAME: str = "master"
    KEYCLOAK_CLIENT_ID: str = "rag-backend"
    KEYCLOAK_CLIENT_SECRET: str = ""
    KEYCLOAK_ALGORITHM: str = "RS256"


keycloak_settings = KeycloakSettings()

# Initialize Keycloak OpenID Client
keycloak_openid = KeycloakOpenID(
    server_url=keycloak_settings.KEYCLOAK_SERVER_URL,
    client_id=keycloak_settings.KEYCLOAK_CLIENT_ID,
    realm_name=keycloak_settings.KEYCLOAK_REALM_NAME,
    client_secret_key=keycloak_settings.KEYCLOAK_CLIENT_SECRET,
)


from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware."""

    def __init__(self, app):
        super().__init__(app)
        self.security = HTTPBearer()
        self._jwks = None
        self._public_key_pem = None
        self._jwks_by_issuer = {}

    def _get_jwks(self):
        """Fetch and cache JWKS from Keycloak."""
        if self._jwks is None:
            jwks = keycloak_openid.certs()
            self._jwks = json.loads(jwks) if isinstance(jwks, str) else jwks
        return self._jwks

    def _refresh_jwks(self):
        """Force refresh JWKS (in case of key rotation)."""
        jwks = keycloak_openid.certs()
        self._jwks = json.loads(jwks) if isinstance(jwks, str) else jwks
        return self._jwks

    def _get_jwks_for_issuer(self, issuer: str):
        """Fetch JWKS for a given issuer and cache it."""
        if not issuer:
            return None
        if issuer in self._jwks_by_issuer:
            return self._jwks_by_issuer[issuer]
        jwks_url = issuer.rstrip("/") + "/protocol/openid-connect/certs"
        # Patch for internal resolution if running in k8s/docker and issuer is external
        if "keycloak.rag.localhost" in jwks_url:
            jwks_url = jwks_url.replace("keycloak.rag.localhost", "rag-keycloak-http:80")
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        self._jwks_by_issuer[issuer] = jwks
        return jwks

    def _refresh_jwks_for_issuer(self, issuer: str):
        """Refresh JWKS for a given issuer."""
        if not issuer:
            return None
        jwks_url = issuer.rstrip("/") + "/protocol/openid-connect/certs"
        # Patch for internal resolution if running in k8s/docker and issuer is external
        if "keycloak.rag.localhost" in jwks_url:
            jwks_url = jwks_url.replace("keycloak.rag.localhost", "rag-keycloak-http:80")
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        self._jwks_by_issuer[issuer] = jwks
        return jwks

    def _get_public_key_pem(self):
        """Fetch and cache the PEM-formatted public key."""
        if self._public_key_pem is None:
            raw_public_key = keycloak_openid.public_key().strip()
            self._public_key_pem = (
                raw_public_key
                if raw_public_key.startswith("-----BEGIN")
                else "-----BEGIN PUBLIC KEY-----\n" + raw_public_key + "\n-----END PUBLIC KEY-----"
            )
        return self._public_key_pem
    
    def _refresh_public_key_pem(self):
        """Force refresh PEM public key (in case of key rotation)."""
        raw_public_key = keycloak_openid.public_key().strip()
        self._public_key_pem = (
            raw_public_key
            if raw_public_key.startswith("-----BEGIN")
            else "-----BEGIN PUBLIC KEY-----\n" + raw_public_key + "\n-----END PUBLIC KEY-----"
        )
        return self._public_key_pem

    def _decode_with_jwks(self, token: str) -> dict:
        """Decode using JWKS (kid-aware)."""
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if not alg:
            raise ValueError("Token missing 'alg' header")
        kid = header.get("kid")
        payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        issuer = payload.get("iss")

        def _decode_with_keys(jwks_obj, source_name: str):
            keys = jwks_obj.get("keys", []) if isinstance(jwks_obj, dict) else []
            available_kids = [k.get("kid") for k in keys if k.get("kid")]
            if kid and kid not in available_kids:
                raise ValueError(f"kid {kid} not found in JWKS ({source_name}); available: {available_kids}")
            key_obj = None
            if kid:
                for candidate in keys:
                    if candidate.get("kid") == kid:
                        key_obj = candidate
                        break
            if key_obj is None and len(keys) == 1:
                key_obj = keys[0]
            if key_obj is None:
                raise ValueError(f"No suitable JWKS key available ({source_name}); available kids: {available_kids}")

            try:
                algorithm = jwt.algorithms.get_default_algorithms()[alg]
            except KeyError:
                raise ValueError(f"Unsupported algorithm: {alg}")

            public_key = algorithm.from_jwk(json.dumps(key_obj))
            return jwt.decode(
                token,
                key=public_key,
                algorithms=[alg],
                options={"verify_aud": False},
                leeway=10,
            )

        jwks_sources = []
        if issuer:
            jwks_sources.append(("issuer", self._get_jwks_for_issuer(issuer), lambda: self._refresh_jwks_for_issuer(issuer)))
        jwks_sources.append(("default", self._get_jwks(), self._refresh_jwks))

        last_error = None
        for name, jwks_obj, refresher in jwks_sources:
            try:
                return _decode_with_keys(jwks_obj, name)
            except InvalidSignatureError as sig_err:
                logger.info("JWKS signature failed (kid=%s, alg=%s, source=%s), refreshing and retrying", kid, alg, name)
                last_error = sig_err
                try:
                    return _decode_with_keys(refresher(), name + "-refreshed")
                except Exception as refresh_error:
                    last_error = refresh_error
                    continue
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise ValueError("JWKS verification failed with no available sources")

    def _decode_with_pem(self, token: str) -> dict:
        """Decode using PEM public key as a fallback."""
        header = jwt.get_unverified_header(token)
        alg = header.get("alg") or keycloak_settings.KEYCLOAK_ALGORITHM
        try:
            return jwt.decode(
                token,
                key=self._get_public_key_pem(),
                algorithms=[alg],
                options={"verify_aud": False},
                leeway=10,
            )
        except InvalidSignatureError:
            logger.info("PEM signature failed (alg=%s), refreshing public key and retrying", alg)
            return jwt.decode(
                token,
                key=self._refresh_public_key_pem(),
                algorithms=[alg],
                options={"verify_aud": False},
                leeway=10,
            )

    async def dispatch(self, request: Request, call_next):
        """Authenticate request."""
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for docs and openapi
        openapi_paths = {"/docs", "/openapi.json", "/redoc", "/api/docs", "/api/openapi.json", "/api/redoc"}
        if request.url.path in openapi_paths:
            return await call_next(request)

        # Allow internal health/readiness without auth
        if request.url.path in {"/health", "/health/ready", "/health/live", "/ready", "/live"}:
            return await call_next(request)

        credentials: Optional[HTTPAuthorizationCredentials] = await self.security(request)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials
        try:
            # Verify token
            # Try JWKS first (kid-aware) and fall back to realm public key PEM if needed.
            try:
                token_info = self._decode_with_jwks(token)
            except Exception as jwks_error:
                logger.warning("JWKS verification failed, retrying with PEM: %s", jwks_error)
                token_info = self._decode_with_pem(token)

            # Extract Tenant ID (Organization) - must be present
            tenant_id = token_info.get("tenant_id")
            if not tenant_id:
                logger.warning("No tenant ID found in token for user %s", token_info.get("preferred_username"))
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing tenant_id claim in token")

            set_tenant_id(tenant_id)
            logger.info(f"Authenticated user {token_info.get('preferred_username')} for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return await call_next(request)
