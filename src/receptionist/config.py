from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    dry_run: bool = True
    secret_key: str = "dev-secret-change-me"

    tidb_host: str = ""
    tidb_port: int = 4000
    tidb_user: str = "root"
    tidb_password: str = ""
    tidb_database: str = "ai_receptionist"
    tidb_ssl_mode: str = "preferred"
    tidb_ca_path: str = ""

    database_url: str = "sqlite+aiosqlite:///./dev.db"

    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""

    redis_url: str = "redis://localhost:6379/0"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@100solutionz.com"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""

    api_key_header: str = "X-API-Key"
    api_rate_limit: int = 100

    dashboard_port: int = 8501
    api_port: int = 8000

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url_async(self) -> str:
        if self.tidb_host:
            return (
                f"mysql+aiomysql://{self.tidb_user}:{self.tidb_password}"
                f"@{self.tidb_host}:{self.tidb_port}/{self.tidb_database}"
            )
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
