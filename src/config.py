from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str
    WEBHOOK_URL: str

    # Agent service
    AGENT_SERVICE_URL: str
    LANGGRAPH_ASSISTANT_ID: str
    LANGGRAPH_API_KEY: str  # fixed typo: LAGGRAPH -> LANGGRAPH

    # Database
    DATABASE_URL: str  # must use postgresql+asyncpg:// scheme

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # BOT_TOKEN and bot_token both work
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()  # module-level singleton still works