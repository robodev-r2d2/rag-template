import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request, HTTPException
from rag_core_api.auth import AuthMiddleware
from rag_core_lib.context import clear_tenant_id, get_tenant_id


@pytest.fixture
def auth_middleware():
    app = MagicMock()
    return AuthMiddleware(app)


@pytest.fixture(autouse=True)
def reset_tenant_context():
    clear_tenant_id()
    yield
    clear_tenant_id()


@pytest.mark.asyncio
async def test_auth_middleware_success(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/chat"
    request.headers = {"Authorization": "Bearer valid_token"}

    async def mock_security_call(req):
        return MagicMock(credentials="valid_token")

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware, "_decode_with_jwks", return_value={"preferred_username": "user", "tenant_id": "tenant-a"}
    ):
        async def call_next(req):
            return "response"

        await auth_middleware.dispatch(request, call_next)

    assert get_tenant_id() == "tenant-a"


@pytest.mark.asyncio
async def test_auth_middleware_missing_tenant_claim(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/chat"
    request.headers = {"Authorization": "Bearer valid_token"}

    async def mock_security_call(req):
        return MagicMock(credentials="valid_token")

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware, "_decode_with_jwks", return_value={"preferred_username": "user"}
    ):
        async def call_next(req):
            return "response"

        with pytest.raises(HTTPException) as excinfo:
            await auth_middleware.dispatch(request, call_next)

    assert excinfo.value.status_code == 403
    assert "tenant_id" in excinfo.value.detail
    assert get_tenant_id() is None


@pytest.mark.asyncio
async def test_auth_middleware_invalid_token(auth_middleware):
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/chat"
    request.headers = {"Authorization": "Bearer invalid_token"}

    async def mock_security_call(req):
        return MagicMock(credentials="invalid_token")

    with patch.object(auth_middleware, "security", side_effect=mock_security_call), patch.object(
        auth_middleware, "_decode_with_jwks", side_effect=Exception("Invalid token")
    ), patch.object(
        auth_middleware, "_decode_with_pem", side_effect=Exception("Invalid token")
    ):
        async def call_next(req):
            return "response"

        with pytest.raises(HTTPException) as excinfo:
            await auth_middleware.dispatch(request, call_next)

    assert excinfo.value.status_code == 401
