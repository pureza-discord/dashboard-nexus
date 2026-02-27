import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "leads.db"))
FRONTEND_DIST = str(BASE_DIR / "frontend" / "dist")
ASSETS_DIR = str(BASE_DIR / "assets")

SECRET_KEY = os.getenv("DASHBOARD_SECRET", "nexus-leads-secret-change-me-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))

RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

AVERAGE_DEAL_VALUE = float(os.getenv("AVERAGE_DEAL_VALUE", "2500"))
