"""Application configuration loaded from environment variables."""

from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for MATRIX Intel Backend API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "MATRIX Intel API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:5173"

    # Database Configuration (SQLite default for dev; PostgreSQL/Db2 for LinuxONE)
    DATABASE_URL: str = "sqlite:///./data/matrix.db"
    DB_ECHO: bool = False

    # Worker 2 ML Module Integration Configuration
    ML_MODEL_ENABLED: bool = False
    ML_MODEL_ARTIFACT_PATH: str = "./app/ml/artifacts/model.joblib"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        if isinstance(self.CORS_ORIGINS, list):
            origins = [o.strip() for o in self.CORS_ORIGINS if o.strip()]
        else:
            origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

        # Reject wildcard origin in production for security compliance
        if self.ENVIRONMENT.lower() == "production" and "*" in origins:
            raise ValueError("Wildcard '*' CORS origin is not permitted in production environment.")

        return origins or ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
