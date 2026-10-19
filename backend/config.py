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
    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    streamlit_port: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    gemini_model_id: str = os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
    openrouter_model_id: str = os.getenv("OPENROUTER_MODEL_ID", "openai/gpt-4o-mini")
    provider_timeout_seconds: float = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "30"))
    provider_max_attempts: int = int(os.getenv("PROVIDER_MAX_ATTEMPTS", "3"))
    provider_max_retry_delay_seconds: float = float(
        os.getenv("PROVIDER_MAX_RETRY_DELAY_SECONDS", "2")
    )
    judge_enabled: bool = os.getenv("JUDGE_ENABLED", "false").lower() == "true"
    judge_provider: str = os.getenv("JUDGE_PROVIDER", "openrouter").strip().lower()
    judge_model_id: str = os.getenv("JUDGE_MODEL_ID", "openai/gpt-4o-mini")
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
            "CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
