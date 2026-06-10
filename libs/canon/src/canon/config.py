"""Application configuration with singleton pattern."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CanonSys configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CANON_",
        env_file=".env",
        extra="ignore",
    )

    # Database
    database_url: SecretStr
    database_pool_size: int = 15

    # Application
    debug: bool = False
    environment: str = "development"

    # Security
    secret_key: SecretStr | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
