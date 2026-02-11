import pytest
from unittest.mock import MagicMock, patch

from rag_core_api.auth import AuthMiddleware


@pytest.fixture
def auth_middleware():
    app = MagicMock()
    return AuthMiddleware(app)


def test_get_jwks_for_issuer_url_replacement(auth_middleware):
    auth_middleware._trusted_issuers = {"http://keycloak.rag.localhost/auth/realms/rag"}
    with patch("rag_core_api.auth.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": []}
        mock_get.return_value = mock_response

        auth_middleware._get_jwks_for_issuer("http://keycloak.rag.localhost/auth/realms/rag")

        # Verify that the URL was replaced
        mock_get.assert_called_with(
            "http://rag-keycloak-http:80/auth/realms/rag/protocol/openid-connect/certs",
            timeout=5,
        )


def test_get_jwks_for_issuer_rejects_untrusted_issuer(auth_middleware):
    auth_middleware._trusted_issuers = {"http://trusted.example/realms/rag"}
    with patch("rag_core_api.auth.requests.get") as mock_get:
        with pytest.raises(ValueError):
            auth_middleware._get_jwks_for_issuer("http://evil.example/realms/rag")
    mock_get.assert_not_called()


def test_decode_with_jwks_leeway(auth_middleware):
    token = "mock_token"
    auth_middleware._trusted_issuers = {"mock_issuer"}
    with (
        patch("rag_core_api.auth.jwt.get_unverified_header") as mock_header,
        patch("rag_core_api.auth.jwt.decode") as mock_decode,
        patch("rag_core_api.auth.jwt.algorithms.get_default_algorithms") as mock_alg,
    ):
        mock_header.return_value = {"alg": "RS256", "kid": "mock_kid"}
        # First decode for payload
        mock_decode.side_effect = [
            {"iss": "mock_issuer"},  # payload
            {"sub": "user", "iss": "mock_issuer"},  # final decode
        ]

        # Mock JWKS fetch
        auth_middleware._get_jwks_for_issuer = MagicMock(return_value={"keys": [{"kid": "mock_kid"}]})
        # Mock default JWKS to avoid error
        auth_middleware._get_jwks = MagicMock(return_value={"keys": []})

        # Mock algorithm
        mock_algo_instance = MagicMock()
        mock_alg.return_value = {"RS256": mock_algo_instance}

        auth_middleware._decode_with_jwks(token)

        # Verify leeway was passed to the second decode call
        call_args = mock_decode.call_args_list[1]
        _, kwargs = call_args
        assert kwargs.get("leeway") == 10
