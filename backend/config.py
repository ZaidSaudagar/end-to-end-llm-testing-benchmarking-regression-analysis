import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv(
        "APP_NAME",
        "End-to-End LLM Testing, Benchmarking and Regression Analysis",
    )
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    backend_api_key: str = os.getenv("BACKEND_API_KEY", "")
    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_base_url: str = os.getenv("MINIMAX_BASE_URL", "https://kiraai.vn/api/v1")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    gemini_model_id: str = os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
    minimax_model_id: str = os.getenv(
        "MINIMAX_MODEL_ID", os.getenv("MINIMAX_MODEL", "kira-3.5-flash")
    )
    groq_model_id: str = os.getenv("GROQ_MODEL_ID", "qwen/qwen3.8-27b")
    provider_timeout_seconds: float = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "30"))
    provider_max_attempts: int = int(os.getenv("PROVIDER_MAX_ATTEMPTS", "3"))
    provider_max_retry_delay_seconds: float = float(
        os.getenv("PROVIDER_MAX_RETRY_DELAY_SECONDS", "2")
    )
    judge_enabled: bool = os.getenv("JUDGE_ENABLED", "false").lower() == "true"
    judge_provider: str = os.getenv("JUDGE_PROVIDER", "minimax").strip().lower()
    judge_model_id: str = os.getenv("JUDGE_MODEL_ID", "kira-3.5-flash")
    judge_max_response_attempts: int = int(os.getenv("JUDGE_MAX_RESPONSE_ATTEMPTS", "2"))
    judge_repetitions: int = int(os.getenv("JUDGE_REPETITIONS", "1"))
    embedding_model_id: str = os.getenv(
        "EMBEDDING_MODEL_ID", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_model_revision: str = os.getenv(
        "EMBEDDING_MODEL_REVISION", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        ).split(",")
        if origin.strip()
    )
    allowed_hosts: tuple[str, ...] = tuple(
        host.strip()
        for host in os.getenv(
            "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,backend"
        ).split(",")
        if host.strip()
    )

    def __post_init__(self) -> None:
        if self.environment.strip().lower() != "production":
            return
        if self.debug:
            raise ValueError("DEBUG must be false when ENVIRONMENT=production")
        if len(self.backend_api_key) < 32:
            raise ValueError("BACKEND_API_KEY must contain at least 32 characters in production")
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must contain explicit origins in production")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS must contain explicit hosts in production")


settings = Settings()
