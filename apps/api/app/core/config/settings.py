# app/core/config/settings.py
"""
应用配置模块

配置默认值只服务本地 Docker 开发环境；测试、预发布和生产环境应通过环境变量覆盖。
字段使用 validation_alias 显式绑定环境变量名，避免 Python 属性名和部署变量名混淆。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置对象。

    Pydantic Settings 会自动读取环境变量和 .env 文件。业务代码统一通过
    get_settings() 获取配置，避免在模块导入阶段重复解析环境。
    """

    # --- 应用基础信息 ---
    app_name: str = "MakersHub API"  # API 文档和健康检查中展示的服务名称
    app_env: str = Field("local", validation_alias="APP_ENV")  # local/staging/production 等环境标识
    api_prefix: str = "/api/v1"  # 第一阶段正式 API 统一前缀

    # --- 令牌配置 ---
    jwt_secret_key: str = Field(
        "ChangeMeInProduction",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        60 * 24 * 7,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # --- 微信小程序登录配置 ---
    wechat_app_id: str | None = Field(None, validation_alias="WECHAT_APP_ID")
    wechat_app_secret: str | None = Field(None, validation_alias="WECHAT_APP_SECRET")
    wechat_code2session_url: str = Field(
        "https://api.weixin.qq.com/sns/jscode2session",
        validation_alias="WECHAT_CODE2SESSION_URL",
    )

    # --- 数据库配置 ---
    database_url: str = Field(
        "mysql+aiomysql://makershub:makershub@mysql:3306/makershub_dev",
        validation_alias="DATABASE_URL",
    )
    database_echo: bool = Field(False, validation_alias="DATABASE_ECHO")  # 本地调试 SQL 时才开启

    # --- MinIO / 对象存储配置 ---
    minio_endpoint: str = Field("minio:9000", validation_alias="MINIO_ENDPOINT")
    minio_access_key: str = Field("makershub", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field("makershub_minio", validation_alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(False, validation_alias="MINIO_SECURE")
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

    # --- 跨域配置 ---
    cors_origins: str = Field(
        "http://localhost:5173,http://localhost:5174,http://localhost:5175",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def allow_origins(self) -> list[str]:
        """把逗号分隔的 CORS 配置转换成 FastAPI 需要的列表。"""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allow_dev_wechat_login(self) -> bool:
        """是否允许使用开发态 openid 登录。

        本地开发和自动化测试无法直接拿到真实微信 code，因此允许 dev_openid。
        预发布和生产环境必须关闭，避免绕过微信 code2session。
        """

        return self.app_env in {"local", "test", "development"}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次依赖注入都重新读取 .env。"""

    return Settings()
