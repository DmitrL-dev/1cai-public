import requests
import logging
import unittest
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestCoreApps(unittest.TestCase):
    def check_url(self, name, url, expected_codes=[200]):
        """Helper to check if a URL is reachable and returns expected status code."""
        logger.info(f"Checking {name} at {url}...")
        try:
            response = requests.get(url, timeout=5)
            logger.info(f"{name} returned {response.status_code}")
            self.assertIn(
                response.status_code, expected_codes, f"{name} returned unexpected code {response.status_code}"
            )
        except requests.exceptions.ConnectionError:
            self.fail(f"{name} is not reachable at {url}")
        except Exception as e:
            self.fail(f"{name} check failed with error: {e}")

    def test_nocobase_availability(self):
        """Test NocoBase availability."""
        # NocoBase usually returns 200 OK on root
        self.check_url("NocoBase", "http://localhost:13000", expected_codes=[200])

    def test_vscode_availability(self):
        """Test VS Code Server availability."""
        # VS Code redirects to login (302) or shows login page (200) depending on path
        # It might return 401 if auth is required immediately
        # We accept 200, 302, 401 as signs of life
        self.check_url("VS Code", "http://localhost:8000", expected_codes=[200, 302, 401])

    def test_portainer_availability(self):
        """Test Portainer availability."""
        # Portainer usually returns 200 (login page)
        self.check_url("Portainer", "http://localhost:9000", expected_codes=[200])


if __name__ == "__main__":
    # Give services a moment if just restarted
    time.sleep(2)
    unittest.main()
