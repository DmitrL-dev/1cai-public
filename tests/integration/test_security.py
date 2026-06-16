import unittest
import requests
import time
import logging
import urllib3

# Suppress insecure request warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSecurityLayer(unittest.TestCase):
    def setUp(self):
        self.wazuh_url = "https://localhost:443" # Mapped from 5601
        self.opa_url = "http://localhost:8181"

    def test_wazuh_dashboard_availability(self):
        """Test if Wazuh Dashboard is reachable."""
        logger.info(f"Checking Wazuh Dashboard at {self.wazuh_url}...")
        try:
            # Wazuh uses self-signed certs by default
            response = requests.get(self.wazuh_url, verify=False, timeout=10)
            # It might redirect to /app/login or return 200
            self.assertIn(response.status_code, [200, 302, 401, 403])
            logger.info("Wazuh Dashboard returned valid status")
        except requests.exceptions.ConnectionError:
            self.fail("Wazuh Dashboard is not reachable")

    def test_opa_availability(self):
        """Test if OPA is reachable."""
        logger.info(f"Checking OPA at {self.opa_url}...")
        try:
            # OPA health check endpoint
            response = requests.get(f"{self.opa_url}/health", timeout=5)
            self.assertEqual(response.status_code, 200)
            logger.info("OPA returned 200 OK")
        except requests.exceptions.ConnectionError:
            self.fail("OPA is not reachable")

if __name__ == "__main__":
    unittest.main()
