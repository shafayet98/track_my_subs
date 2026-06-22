"""Application settings, loaded once from the environment.

All configuration flows through this module — never call os.getenv elsewhere.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-opus-4-8"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/track_my_subs",
        alias="DATABASE_URL",
    )

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = Field(default=60, alias="JWT_EXPIRES_MINUTES")

    # Encryption for stored OAuth refresh tokens (Fernet key, base64, 32 bytes)
    token_encryption_key: str = Field(default="", alias="TOKEN_ENCRYPTION_KEY")

    # Google OAuth (Gmail, read-only)
    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/accounts/gmail/callback",
        alias="GOOGLE_OAUTH_REDIRECT_URI",
    )
    gmail_scope: str = "https://www.googleapis.com/auth/gmail.readonly"

    # App
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")

    # Scan: how far back (days) the candidate-email search looks. ~2 months so a
    # first scan reliably catches at least one billing cycle for monthly subs.
    scan_lookback_days: int = Field(default=60, alias="SCAN_LOOKBACK_DAYS")

    # Notifications (renewal/trial/missed-payment alert emails via SES).
    # Sender must be a verified SES identity. An empty sender disables sending
    # (the worker logs and skips) so local/dev runs never hit SES.
    aws_region: str = Field(default="ap-southeast-2", alias="AWS_REGION")
    ses_sender: str = Field(default="", alias="SES_SENDER")
    # Public app URL used in email links ("manage your subscriptions").
    app_base_url: str = Field(default="http://localhost:5173", alias="APP_BASE_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
