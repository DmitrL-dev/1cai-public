"""
Gateway Configuration
"""

# Service configuration
SERVICES_CONFIG = {
    "assistants": {
        "url": "http://localhost:8002",
        "health_endpoint": "/api/assistants/health",
        "name": "AI Assistants Service",
        "timeout": 30.0,
    },
    "ml": {
        "url": "http://localhost:8001",
        "health_endpoint": "/health",
        "name": "ML System Service",
        "timeout": 30.0,
    },
    "risk": {
        "url": "http://localhost:8003",
        "health_endpoint": "/health",
        "name": "Risk Management Service",
        "timeout": 30.0,
    },
    "metrics": {
        "url": "http://localhost:8004",
        "health_endpoint": "/health",
        "name": "Metrics Service",
        "timeout": 30.0,
    },
}
