"""
Rate limiting configuration for Archi API endpoints
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance
limiter = Limiter(key_func=get_remote_address)

# Rate limit configurations
ARCHI_EXPORT_RATE_LIMIT = "5/minute"  # 5 exports per minute per IP
ARCHI_IMPORT_RATE_LIMIT = "3/minute"  # 3 imports per minute per IP (more expensive)
ARCHI_HEALTH_RATE_LIMIT = "30/minute"  # 30 health checks per minute
