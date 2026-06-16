import requests
import logging
import unittest
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestIntegrationBus(unittest.TestCase):
    def check_url(self, name, url, expected_codes=[200]):
        """Helper to check if a URL is reachable and returns expected status code."""
        logger.info(f"Checking {name} at {url}...")
        try:
            response = requests.get(url, timeout=5)
            logger.info(f"{name} returned {response.status_code}")
            self.assertIn(response.status_code, expected_codes, f"{name} returned unexpected code {response.status_code}")
        except requests.exceptions.ConnectionError:
            self.fail(f"{name} is not reachable at {url}")
        except Exception as e:
            self.fail(f"{name} check failed with error: {e}")

    def test_rabbitmq_management_availability(self):
        """Test RabbitMQ Management UI availability."""
        # RabbitMQ Management UI usually returns 200 OK on root
        self.check_url("RabbitMQ Management", "http://localhost:15672", expected_codes=[200])

if __name__ == "__main__":
    unittest.main()
