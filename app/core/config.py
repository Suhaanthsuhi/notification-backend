from functools import lru_cache
from typing import Annotated
from pydantic import BeforeValidator, computed_field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

def parse_cors(val: str | list[str]) -> list[str]:
    if isinstance(val, str):
        return [origin.strip() for origin in val.split(",")]
    return val

class Settings(BaseSettings):
    #Application
    service_name: str = "FastAPI Backend"
    env: str = "dev"
    debug: bool = True

    # NoDecode stops pydantic-settings from JSON-decoding this list field when it
    # comes from a .env / env var, so parse_cors can handle a comma-separated string.
    allowed_origins: Annotated[list[str], NoDecode, BeforeValidator(parse_cors)] = ["*"]

    # Security
    master_api_key: str = "12345678-unsafe-master-key"
    secret_key: str = "changeme-set-a-real-SECRET_KEY-in-your-env-file-min-32-bytes!"

    # Cache / Redis
    redis_url: str | None = None

    # Database Components
    db_dialect: str = "postgresql"
    db_driver: str = "asyncpg"
    db_user: str | None = None
    db_password: str | None = None
    db_host: str | None = None
    db_port: str = "5432"
    db_name: str | None = None
    db_supports_schema: bool = False

    @model_validator(mode="after")
    def validate_env(self):
        env = self.env.lower()
        if env not in ["dev", "test", "local", "prod"]:
            raise ValueError(
                f"Invalid ENV value: {env}. Must be one of: dev, test, local, prod."
            )
        return self

    @model_validator(mode="after")
    def validate_production_defaults(self):
        if self.env.lower() in ["dev", "test", "local"]:
            return self

        if self.secret_key.startswith("changeme-"):
            raise ValueError(
                "You must set a real SECRET_KEY in your .env file for production!"
            )
        
        if self.master_api_key.startswith("12345678-unsafe-master-key"):
            raise ValueError(
                "You must set a real MASTER_API_KEY in your .env file for production!"
            )
        return self

    @property
    def db_schema(self):
        sch = self.service_name.replace("-", "_")
        return sch

    @computed_field
    @property
    def engine_str(self) -> str:
        if self.db_host:
            return (
                f"{self.db_dialect}+{self.db_driver}://"
                f"{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return "sqlite+aiosqlite:///:memory:"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

__all__ = ["settings", "get_settings"]