"""Desktop auth configuration.

Point USQLC_API_URL at the FastAPI backend (local dev or the VPS).
"""

import os

API_BASE_URL = os.environ.get("USQLC_API_URL", "http://localhost:8000")
