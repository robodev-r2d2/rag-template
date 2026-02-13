import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, Request

from rag_core_api.auth import AuthMiddleware
from rag_core_lib.context import (
    clear_principal,
    clear_requested_space_ids,
    clear_target_space_id,
    clear_tenant_id,
    get_principal,
    get_tenant_id,
)


@pytest.fixture(autouse=True)
def reset_context():
    clear_principal()
    clear_requested_space_ids()
    clear_target_space_id()
    clear_tenant_id()
    yield
    clear_principal()
    clear_requested_space_ids()
    clear_target_space_id()
    clear_tenant_id()


@pytest.fixture
def auth_middleware(monkeypatch):
    monkeypatch.delenv("ALLOW_ANONYMOUS_CHAT", raising=False)
    app = MagicMock()
    return AuthMiddleware(app)


@pytest.mark.asyncio
async def test_auth_middleware_success(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/chat/session-1"
    request.headers = {"Authorization": "Bearer valid_token"}

    async def mock_security_call(_request):
        return MagicMock(credentials="valid_token")

    observed = {}

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware,
        "_decode_with_jwks",
        return_value={
            "preferred_username": "user",
            "tenant_id": "tenant-a",
            "allowed_tenant_ids": ["tenant-a", "tenant-b"],
            "allowed_domain_ids": ["finance"],
            "can_write_shared_domain": True,
        },
    ):

        async def call_next(_request):
            observed["tenant_id"] = get_tenant_id()
            observed["principal"] = get_principal()
            return "response"

        await auth_middleware.dispatch(request, call_next)

    assert observed["tenant_id"] == "tenant-a"
    assert observed["principal"] is not None
    assert observed["principal"].allowed_tenant_ids == ["tenant-a", "tenant-b"]
    assert observed["principal"].allowed_domain_ids == ["finance"]


@pytest.mark.asyncio
async def test_auth_middleware_missing_tenant_claim(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/chat/session-2"
    request.headers = {"Authorization": "Bearer valid_token"}

    async def mock_security_call(_request):
        return MagicMock(credentials="valid_token")

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware, "_decode_with_jwks", return_value={"preferred_username": "user"}
    ):

        async def call_next(_request):
            return "response"

        with pytest.raises(HTTPException) as excinfo:
            await auth_middleware.dispatch(request, call_next)

    assert excinfo.value.status_code == 403
    assert "tenant_id" in excinfo.value.detail


@pytest.mark.asyncio
async def test_auth_middleware_invalid_token(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/chat/session-3"
    request.headers = {"Authorization": "Bearer invalid_token"}

    async def mock_security_call(_request):
        return MagicMock(credentials="invalid_token")

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware, "_decode_with_jwks", side_effect=Exception("Invalid token")
    ), patch.object(auth_middleware, "_decode_with_pem", side_effect=Exception("Invalid token")):

        async def call_next(_request):
            return "response"

        with pytest.raises(HTTPException) as excinfo:
            await auth_middleware.dispatch(request, call_next)

    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_middleware_allows_anonymous_chat_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS_CHAT", "true")
    middleware = AuthMiddleware(MagicMock())
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/chat/session-4"
    request.headers = {}

    async def mock_security_call(_request):
        return None

    observed = {}

    with patch.object(middleware, "security", side_effect=mock_security_call):

        async def call_next(_request):
            observed["principal"] = get_principal()
            return "response"

        await middleware.dispatch(request, call_next)

    assert observed["principal"] is not None
    assert observed["principal"].is_anonymous is True


@pytest.mark.asyncio
async def test_auth_middleware_allows_anonymous_chat_on_api_prefix_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_ANONYMOUS_CHAT", "true")
    middleware = AuthMiddleware(MagicMock())
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/chat/session-5"
    request.headers = {}

    async def mock_security_call(_request):
        return None

    observed = {}

    with patch.object(middleware, "security", side_effect=mock_security_call):

        async def call_next(_request):
            observed["principal"] = get_principal()
            return "response"

        await middleware.dispatch(request, call_next)

    assert observed["principal"] is not None
    assert observed["principal"].is_anonymous is True
