"""Configurações da aplicação via variáveis de ambiente."""
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Banco de dados
    DATABASE_URL: str = Field(
        default="sqlite:///./tecnotextil.db",
        description="URL de conexão do banco (SQLite ou PostgreSQL)",
    )

    # Segurança JWT
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production-min-32-chars",
        description="Chave secreta para assinar tokens JWT (mín. 32 chars em produção)",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Ambiente
    ENVIRONMENT: str = Field(default="development", description="development, staging, production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()