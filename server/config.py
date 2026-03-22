from server.core.settings import get_settings

settings = get_settings()

APP_NAME = settings.app_name
ENVIRONMENT = settings.environment
API_HOST = settings.api_host
API_PORT = settings.api_port
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
CORS_ORIGINS = settings.cors_origins
CORS_ALLOW_CREDENTIALS = settings.cors_allow_credentials
# Mapping to old names used by middleware and services
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm
TOKEN_EXPIRE_HOURS = settings.access_token_expire_minutes // 60
SCRAPER_MODE = settings.scraper_mode

# Default limits and constants used across the app
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60
COOKIE_DOMAIN = None
COOKIE_SAMESITE = "lax"
COOKIE_SECURE = False
AVERAGE_DEAL_VALUE = 5000

# Auth bootstrapping constants
AUTO_BOOTSTRAP_ADMIN = settings.auto_bootstrap_admin
BOOTSTRAP_ADMIN_PASSWORD = settings.bootstrap_admin_password
BOOTSTRAP_ADMIN_USERNAME = settings.bootstrap_admin_email
