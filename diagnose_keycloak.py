import os
import logging
from keycloak import KeycloakAdmin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_ADMIN = "admin"
KEYCLOAK_ADMIN_PASSWORD = "admin"

def diagnose():
    try:
        logger.info(f"Connecting to {KEYCLOAK_URL}...")
        admin = KeycloakAdmin(
            server_url=KEYCLOAK_URL,
            username=KEYCLOAK_ADMIN,
            password=KEYCLOAK_ADMIN_PASSWORD,
            realm_name="master",
            verify=True
        )
        logger.info("Connected successfully.")
        
        logger.info("Listing realms...")
        realms = admin.get_realms()
        logger.info(f"Found realms: {[r['realm'] for r in realms]}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
