from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./leetbug.db"
    redis_url: str = "redis://localhost:6379/0"
    allowed_origins: str = "http://localhost:8080,http://localhost:5173"
    cookie_secure: bool = False
    session_days: int = 7
    seed_demo_user: bool = False
    demo_password: str = "DebugBetter2026!"
    testing: bool = False
    docker_host: str = "unix:///var/run/docker.sock"
    sandbox_image: str = "leetbug-sandbox:1"
    sandbox_memory_mb: int = 512
    sandbox_timeout_seconds: int = 90
    ai_provider: str = "disabled"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = "qwen2.5-coder:7b"
    ai_timeout_seconds: int = 60
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    embedding_base_url: str = ""
    embedding_model: str = ""
    hint_failure_threshold: int = 2

    @property
    def origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def ai_enabled(self) -> bool:
        return self.ai_provider == "ollama" or (
            self.ai_provider == "openrouter" and bool(self.ai_api_key)
        )

    @property
    def llm_url(self) -> str:
        if self.ai_base_url:
            return self.ai_base_url.rstrip("/")
        return "http://ollama:11434/v1" if self.ai_provider == "ollama" else "https://openrouter.ai/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

