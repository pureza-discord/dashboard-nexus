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
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
SCRAPER_MODE = settings.scraper_mode
