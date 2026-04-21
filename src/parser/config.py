from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    """
    Application settings loaded from environment variables.

    This class centralizes all configuration required for:
    - database connection
    - debugging / logging behavior
    """

    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))

    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "csfloat")

    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"

    @property
    def DATABASE_URL(self) -> str:
        """
        Full SQLAlchemy PostgreSQL connection string.

        Returns:
            str: formatted database URL
        """
        return (
            f"postgresql://{self.DB_USER}:"
            f"{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:"
            f"{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )


settings = Settings()
