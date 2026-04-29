from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MakersHub API"
    app_env: str = Field("local", validation_alias="APP_ENV")
    api_prefix: str = "/api/v1"

    database_url: str = Field(
        "mysql+aiomysql://makershub:makershub@mysql:3306/makershub_v2",
        validation_alias="DATABASE_URL",
    )
    minio_endpoint: str = Field("minio:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field("makershub", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field("makershub_minio", validation_alias="MINIO_SECRET_KEY")
    minio_bucket_name: str = Field("makershub-local", validation_alias="MINIO_BUCKET_NAME")
    minio_avatar_bucket: str = Field(
        "makershub-avatars-local",
        validation_alias="MINIO_AVATAR_BUCKET",
    )
    minio_public_bucket: str = Field(
        "makershub-public-local",
        validation_alias="MINIO_PUBLIC_BUCKET",
    )
    minio_resource_bucket: str = Field(
        "makershub-resources-local",
        validation_alias="MINIO_RESOURCE_BUCKET",
    )
    minio_project_bucket: str = Field(
        "makershub-projects-local",
        validation_alias="MINIO_PROJECT_BUCKET",
    )
    minio_temp_bucket: str = Field(
        "makershub-temp-local",
        validation_alias="MINIO_TEMP_BUCKET",
    )

    cors_origins: str = Field(
        "http://localhost:5173,http://localhost:5174,http://localhost:5175",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
