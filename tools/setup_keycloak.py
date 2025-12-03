import logging
import os
import sys
from keycloak import KeycloakAdmin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allow overrides via env vars so local/prod credentials work.
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak.rag.localhost/auth/")
USERNAME = os.getenv("KEYCLOAK_ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = os.getenv("KEYCLOAK_REALM", "rag")

def setup_keycloak():
    try:
        # Disable auto refresh to avoid refresh-token issues in short-lived scripts.
        keycloak_admin = KeycloakAdmin(
            server_url=KEYCLOAK_URL,
            username=USERNAME,
            password=PASSWORD,
            realm_name="master",
            verify=False,
            auto_refresh_token=[],
        )
    except Exception as e:
        logger.error(f"Failed to connect to Keycloak: {e}")
        sys.exit(1)

    # Create Realm
    try:
        if keycloak_admin.get_realm(REALM_NAME):
            logger.info(f"Realm '{REALM_NAME}' already exists.")
    except Exception as e:
        logger.error(f"Failed to get realm '{REALM_NAME}': {e}")
        keycloak_admin.create_realm(payload={"realm": REALM_NAME, "enabled": True})
        logger.info(f"Realm '{REALM_NAME}' created.")

    # Switch to rag realm
    try:
        keycloak_admin = KeycloakAdmin(
            server_url=KEYCLOAK_URL,
            username=USERNAME,
            password=PASSWORD,
            realm_name=REALM_NAME,
            verify=False,
        )
    except Exception as e:
        logger.error(f"Failed to connect to Keycloak: {e}")
        sys.exit(1)

    # Create Frontend Client (Public)
    # Create or Update Frontend Client (Public)
    client_id = "rag-frontend"
    redirect_uris = [
        "http://rag.localhost/*",
        "http://admin.rag.localhost/*",
        "http://localhost:4200/*",
        "*" 
    ]
    all_clients = keycloak_admin.get_clients()
    clients = [c for c in all_clients if c.get('clientId') == client_id]
    if clients:
        logger.info(f"Client '{client_id}' already exists. Updating...")
        keycloak_admin.update_client(clients[0]['id'], payload={
            "redirectUris": redirect_uris,
            "webOrigins": ["*"],
            "publicClient": True,
            "directAccessGrantsEnabled": True
        })
        logger.info(f"Client '{client_id}' updated.")
    else:
        keycloak_admin.create_client(payload={
            "clientId": client_id,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "webOrigins": ["*"],
            "redirectUris": redirect_uris,
            "protocol": "openid-connect"
        })
        logger.info(f"Client '{client_id}' created.")

    # Create Backend Client (Confidential/Bearer-only)
    # Note: For simplicity in this dev setup, we might make it public or service-account enabled
    # But usually backend validation just needs the realm keys.
    # Let's create a 'rag-backend' client just in case we need service accounts later.
    client_id = "rag-backend"
    all_clients = keycloak_admin.get_clients()
    clients = [c for c in all_clients if c.get('clientId') == client_id]
    if clients:
        logger.info(f"Client '{client_id}' already exists.")
    else:
        keycloak_admin.create_client(payload={
            "clientId": client_id,
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "protocol": "openid-connect"
        })
        logger.info(f"Client '{client_id}' created.")

    # Create Test User
    user_username = "user"
    user_password = "password"
    users = keycloak_admin.get_users(query={"username": user_username})
    if users:
        logger.info(f"User '{user_username}' already exists.")
    else:
        keycloak_admin.create_user(payload={
            "username": user_username,
            "enabled": True,
            "firstName": "Test",
            "lastName": "User",
            "email": "user@example.com",
            "credentials": [{"value": user_password, "type": "password", "temporary": False}]
        })
        logger.info(f"User '{user_username}' created.")

if __name__ == "__main__":
    setup_keycloak()
