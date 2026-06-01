# app/core/config/settings.py
"""
应用配置模块

配置默认值只服务本地 Docker 开发环境；测试、预发布和生产环境应通过环境变量覆盖。
字段使用 validation_alias 显式绑定环境变量名，避免 Python 属性名和部署变量名混淆。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- 生产配置安全基线 ---

PRODUCTION_ENV = "production"
LOCAL_ONLY_SECRET_VALUES = {
    "changemeinproduction",
    "change-me-in-local-env",
    "change_me_in_local_env_only_32_bytes",
    "makershub",
    "makershub_minio",
}


def is_weak_production_secret(value: str, *, min_length: int) -> bool:
    """判断敏感配置是否仍像本地开发占位值。"""

    normalized = value.strip()
    compact = normalized.lower().replace("-", "_")
    if len(normalized) < min_length:
        return True
    return compact in LOCAL_ONLY_SECRET_VALUES


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
        "change-me-in-local-env-only-32-bytes",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(120, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(30, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # --- 微信小程序登录配置 ---
    wechat_app_id: str | None = Field(None, validation_alias="WECHAT_APP_ID")
    wechat_app_secret: str | None = Field(None, validation_alias="WECHAT_APP_SECRET")
    wechat_code2session_url: str = Field(
        "https://api.weixin.qq.com/sns/jscode2session",
        validation_alias="WECHAT_CODE2SESSION_URL",
    )

    # --- 邮件验证码配置 ---
    email_delivery_mode: str = Field("log", validation_alias="EMAIL_DELIVERY_MODE")
    email_code_expire_minutes: int = Field(5, validation_alias="EMAIL_CODE_EXPIRE_MINUTES")
    email_code_resend_interval_seconds: int = Field(
        60,
        validation_alias="EMAIL_CODE_RESEND_INTERVAL_SECONDS",
    )
    email_code_hourly_limit: int = Field(10, validation_alias="EMAIL_CODE_HOURLY_LIMIT")
    smtp_host: str | None = Field(None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(465, validation_alias="SMTP_PORT")
    smtp_use_ssl: bool = Field(True, validation_alias="SMTP_USE_SSL")
    smtp_username: str | None = Field(None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(None, validation_alias="SMTP_PASSWORD")
    smtp_from_email: str | None = Field(None, validation_alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field("MakersHub", validation_alias="SMTP_FROM_NAME")
    email_home_url: str = Field("https://scumaker.com", validation_alias="EMAIL_HOME_URL")
    email_brand_image_url: str | None = Field(None, validation_alias="EMAIL_BRAND_IMAGE_URL")

    # --- 数据库配置 ---
    database_url: str = Field(
        "mysql+aiomysql://makershub:makershub@mysql:3306/makershub_dev",
        validation_alias="DATABASE_URL",
    )
    database_echo: bool = Field(False, validation_alias="DATABASE_ECHO")  # 本地调试 SQL 时才开启

    # --- 日志配置 ---
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_dir: str = Field("logs", validation_alias="LOG_DIR")
    log_app_file: str = Field(
        "app.log",
        validation_alias=AliasChoices("LOG_APP_FILE", "LOG_FILE"),
    )
    log_error_file: str = Field("error.log", validation_alias="LOG_ERROR_FILE")
    log_request_file: str = Field("request.log", validation_alias="LOG_REQUEST_FILE")
    log_debug_file: str = Field("debug.log", validation_alias="LOG_DEBUG_FILE")
    log_file_enabled: bool = Field(True, validation_alias="LOG_FILE_ENABLED")
    log_console_enabled: bool = Field(True, validation_alias="LOG_CONSOLE_ENABLED")
    log_rotation: str = Field("00:00", validation_alias="LOG_ROTATION")
    log_retention: str = Field("30 days", validation_alias="LOG_RETENTION")
    log_error_retention: str = Field("180 days", validation_alias="LOG_ERROR_RETENTION")
    log_request_retention: str = Field("30 days", validation_alias="LOG_REQUEST_RETENTION")
    log_debug_retention: str = Field("7 days", validation_alias="LOG_DEBUG_RETENTION")
    log_compression: str = Field("zip", validation_alias="LOG_COMPRESSION")
    log_enqueue: bool = Field(True, validation_alias="LOG_ENQUEUE")
    log_debug_file_enabled: bool | None = Field(None, validation_alias="LOG_DEBUG_FILE_ENABLED")

    # --- HTTP 安全边界配置 ---
    security_headers_enabled: bool = Field(True, validation_alias="SECURITY_HEADERS_ENABLED")
    hsts_enabled: bool | None = Field(None, validation_alias="HSTS_ENABLED")
    hsts_max_age_seconds: int = Field(63072000, validation_alias="HSTS_MAX_AGE_SECONDS")
    request_size_limit_enabled: bool = Field(True, validation_alias="REQUEST_SIZE_LIMIT_ENABLED")
    max_request_body_bytes: int = Field(2 * 1024 * 1024, validation_alias="MAX_REQUEST_BODY_BYTES")
    rate_limit_enabled: bool = Field(True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_window_seconds: int = Field(60, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_max_requests: int = Field(300, validation_alias="RATE_LIMIT_MAX_REQUESTS")
    auth_rate_limit_window_seconds: int = Field(60, validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    auth_rate_limit_max_requests: int = Field(30, validation_alias="AUTH_RATE_LIMIT_MAX_REQUESTS")
    rate_limit_exempt_paths: str = Field(
        "/health,/api/v1/health,/api/v1/docs,/api/v1/openapi.json",
        validation_alias="RATE_LIMIT_EXEMPT_PATHS",
    )
    auth_rate_limit_paths: str = Field(
        "/api/v1/auth/wechat/login,"
        "/api/v1/auth/password/login,"
        "/api/v1/auth/email/send-code,"
        "/api/v1/auth/email/first-login,"
        "/api/v1/auth/refresh",
        validation_alias="AUTH_RATE_LIMIT_PATHS",
    )

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        """规范化环境名称，避免大小写或空格导致安全分支失效。"""

        return value.strip().lower()

    @field_validator("email_delivery_mode")
    @classmethod
    def validate_email_delivery_mode(cls, value: str) -> str:
        """校验邮件发送模式。"""

        normalized = value.strip().lower()
        if normalized not in {"log", "smtp"}:
            raise ValueError("EMAIL_DELIVERY_MODE 只能是 log 或 smtp")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """校验日志等级，避免 Loguru 在启动阶段才暴露配置错误。"""

        normalized = value.strip().upper()
        allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError("LOG_LEVEL 不在 Loguru 支持的等级范围内")
        return normalized

    @field_validator(
        "hsts_max_age_seconds",
        "max_request_body_bytes",
        "rate_limit_window_seconds",
        "rate_limit_max_requests",
        "auth_rate_limit_window_seconds",
        "auth_rate_limit_max_requests",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        """校验安全边界相关数值必须为正数。"""

        if value <= 0:
            raise ValueError("安全边界配置必须为正数")
        return value

    @model_validator(mode="after")
    def validate_production_cors(self) -> Settings:
        """生产环境不允许使用通配 CORS。"""

        if self.app_env == PRODUCTION_ENV and "*" in self.allow_origins:
            raise ValueError("生产环境 CORS_ORIGINS 不能使用 *")
        return self

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        """生产环境不允许继续使用本地开发密钥或过短密钥。"""

        if self.app_env != PRODUCTION_ENV:
            return self

        errors: list[str] = []
        if is_weak_production_secret(self.jwt_secret_key, min_length=32):
            errors.append("JWT_SECRET_KEY 必须替换为至少 32 位的生产密钥")
        if self.minio_access_key.strip().lower() == "makershub":
            errors.append("MINIO_ACCESS_KEY 必须替换为生产访问账号")
        if is_weak_production_secret(self.minio_secret_key, min_length=16):
            errors.append("MINIO_SECRET_KEY 必须替换为至少 16 位的生产密钥")
        if errors:
            raise ValueError("；".join(errors))
        return self

    @property
    def should_write_debug_log_file(self) -> bool:
        """
        是否写入 debug 文件。

        生产环境默认关闭 debug 文件，避免低价值日志长期堆积；本地和测试环境默认开启。
        """

        if self.log_debug_file_enabled is not None:
            return self.log_debug_file_enabled
        return self.app_env != PRODUCTION_ENV

    @property
    def should_send_hsts_header(self) -> bool:
        """是否发送 HSTS 响应头。"""

        if self.hsts_enabled is not None:
            return self.hsts_enabled
        return self.app_env == PRODUCTION_ENV

    @property
    def rate_limit_exempt_path_list(self) -> list[str]:
        """把逗号分隔的限流豁免路径转换成列表。"""

        return [path.strip() for path in self.rate_limit_exempt_paths.split(",") if path.strip()]

    @property
    def auth_rate_limit_path_list(self) -> list[str]:
        """把逗号分隔的敏感认证路径转换成列表。"""

        return [path.strip() for path in self.auth_rate_limit_paths.split(",") if path.strip()]

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
