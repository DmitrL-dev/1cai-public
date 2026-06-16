import os
import requests
import logging
import unittest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "1c-enterprise"
CLIENT_ID = "vscode"
CLIENT_SECRET = "vscode-secret-change-me"


class TestIAM(unittest.TestCase):
    def test_login_alice(self):
        """Test login as developer Alice."""
        token_url = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"

        payload = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": "alice",
            "password": "password",
        }

        # Remove client credentials from payload and use Basic Auth
        del payload["client_id"]
        del payload["client_secret"]

        logger.info(f"Attempting login for alice at {token_url}...")
        response = requests.post(token_url, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))

        if response.status_code != 200:
            logger.error(f"Login failed: {response.text}")

        self.assertEqual(response.status_code, 200, "Login failed")

        data = response.json()
        self.assertIn("access_token", data, "No access token returned")
        self.assertIn("refresh_token", data, "No refresh token returned")

        logger.info("Login successful! Access token received.")

        # Verify roles in token (optional, requires decoding JWT)
        # For now, just existence of token is enough proof of authentication.


if __name__ == "__main__":
    unittest.main()
