from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
    ]

    # LLM 配置
    llm_provider: str = "openai"  # openai | anthropic | openai_compatible
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""

    # 输出 token 上限，用于成本控制与生成速度
    llm_max_tokens: int = 4096

    # LLM 调用超时（秒）与重试次数，避免长时间挂起
    llm_timeout: float = 120.0
    llm_max_retries: int = 2

    # 成本控制：每日 LLM 花费上限（元）
    max_daily_cost_cny: float = 50.0
    input_token_price_cny_per_m: float = 3.0  # DeepSeek V4-Pro 缓存未命中价
    output_token_price_cny_per_m: float = 6.0
    cost_safety_factor: float = 1.5  # token 估算安全系数

    # 管理后台下载流量报告
    admin_token: str = ""

    # 预留中间件
    database_url: str = ""
    redis_url: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def analytics_enabled(self) -> bool:
        return bool(self.database_url)


settings = Settings()
