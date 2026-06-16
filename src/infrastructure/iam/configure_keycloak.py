import os
import time
import logging
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_ADMIN = os.getenv("KEYCLOAK_ADMIN", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = "1c-enterprise"


def wait_for_keycloak():
    """Wait for Keycloak to be ready."""
    logger.info(f"Waiting for Keycloak at {KEYCLOAK_URL}...")
    max_retries = 30
    for i in range(max_retries):
        try:
            # Try to initialize KeycloakAdmin to check connection
            KeycloakAdmin(
                server_url=KEYCLOAK_URL,
                username=KEYCLOAK_ADMIN,
                password=KEYCLOAK_ADMIN_PASSWORD,
                realm_name="master",
                verify=True,
            )
            logger.info("Keycloak is ready.")
            return
        except Exception:
            time.sleep(2)
    raise Exception("Keycloak failed to start.")


def configure_realm(keycloak_admin):
    """Create or update the 1c-enterprise realm."""
    logger.info(f"Configuring realm '{REALM_NAME}'...")

    # Check if realm exists
    realms = keycloak_admin.get_realms()
    realm_exists = any(r["realm"] == REALM_NAME for r in realms)

    if not realm_exists:
        keycloak_admin.create_realm(
            payload={
                "realm": REALM_NAME,
                "enabled": True,
                "displayName": "1C AI Enterprise OS",
                "accessTokenLifespan": 3600,  # 1 hour
                "ssoSessionIdleTimeout": 1800,  # 30 mins
            }
        )
        logger.info(f"Realm '{REALM_NAME}' created.")
    else:
        logger.info(f"Realm '{REALM_NAME}' already exists.")


def configure_clients(keycloak_admin):
    """Configure OIDC clients."""
    logger.info("Configuring OIDC clients...")

    clients = [
        {
            "clientId": "vscode",
            "name": "VS Code Server",
            "rootUrl": "http://localhost:8000",
            "adminUrl": "http://localhost:8000",
            "redirectUris": ["http://localhost:8000/*"],
            "webOrigins": ["+"],
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "secret": "vscode-secret-change-me",
            "directAccessGrantsEnabled": True,
            "enabled": True,
        },
        {
            "clientId": "portainer",
            "name": "Portainer",
            "rootUrl": "http://localhost:9000",
            "redirectUris": ["http://localhost:9000/*"],
            "publicClient": False,
            "secret": "portainer-secret-change-me",
            "directAccessGrantsEnabled": True,
            "enabled": True,
        },
        {
            "clientId": "nocobase",
            "name": "NocoBase",
            "rootUrl": "http://localhost:13000",
            "redirectUris": ["http://localhost:13000/*"],
            "publicClient": False,
            "secret": "nocobase-secret-change-me",
            "directAccessGrantsEnabled": True,
            "enabled": True,
        },
    ]

    existing_clients = keycloak_admin.get_clients()
    existing_client_ids = [c["clientId"] for c in existing_clients]

    for client in clients:
        if client["clientId"] in existing_client_ids:
            # Delete to recreate with correct settings (cleaner than update)
            client_uuid = keycloak_admin.get_client_id(client["clientId"])
            keycloak_admin.delete_client(client_uuid)
            logger.info(f"Client '{client['clientId']}' deleted for recreation.")

        keycloak_admin.create_client(payload=client)
        logger.info(f"Client '{client['clientId']}' created.")


def configure_roles(keycloak_admin):
    """Configure Realm Roles."""
    logger.info("Configuring roles...")

    roles = ["developer", "admin", "auditor", "manager"]

    existing_roles = keycloak_admin.get_realm_roles()
    existing_role_names = [r["name"] for r in existing_roles]

    for role in roles:
        if role not in existing_role_names:
            keycloak_admin.create_realm_role(payload={"name": role})
            logger.info(f"Role '{role}' created.")


def configure_users(keycloak_admin):
    """Configure test users."""
    logger.info("Configuring users...")

    users = [
        {
            "username": "alice",
            "email": "alice@corp.local",
            "firstName": "Alice",
            "lastName": "Developer",
            "enabled": True,
            "credentials": [{"value": "password", "type": "password", "temporary": False}],
            "roles": ["developer"],
        },
        {
            "username": "bob",
            "email": "bob@corp.local",
            "firstName": "Bob",
            "lastName": "Manager",
            "enabled": True,
            "credentials": [{"value": "password", "type": "password", "temporary": False}],
            "roles": ["manager", "auditor"],
        },
    ]

    for user_data in users:
        user_roles = user_data.pop("roles")

        # Check if user exists
        user_id = keycloak_admin.get_user_id(user_data["username"])

        if not user_id:
            user_id = keycloak_admin.create_user(payload=user_data)
            logger.info(f"User '{user_data['username']}' created.")
        else:
            # Reset password to ensure it's correct
            keycloak_admin.set_user_password(user_id, "password", temporary=False)

        # Assign roles
        for role in user_roles:
            role_obj = keycloak_admin.get_realm_role(role_name=role)
            keycloak_admin.assign_realm_roles(user_id=user_id, roles=[role_obj])


def main():
    try:
        wait_for_keycloak()

        # 1. Connect to master to create realm
        admin_master = KeycloakAdmin(
            server_url=KEYCLOAK_URL,
            username=KEYCLOAK_ADMIN,
            password=KEYCLOAK_ADMIN_PASSWORD,
            realm_name="master",
            verify=True,
        )

        configure_realm(admin_master)

        # 2. Connect to 1c-enterprise to configure it (auth as master admin)
        admin_realm = KeycloakAdmin(
            server_url=KEYCLOAK_URL,
            username=KEYCLOAK_ADMIN,
            password=KEYCLOAK_ADMIN_PASSWORD,
            realm_name=REALM_NAME,
            user_realm_name="master",
            verify=True,
        )

        configure_clients(admin_realm)
        configure_roles(admin_realm)
        configure_users(admin_realm)

        logger.info("Keycloak configuration completed successfully.")

    except Exception as e:
        logger.error(f"Failed to configure Keycloak: {e}")
        exit(1)


if __name__ == "__main__":
    main()
