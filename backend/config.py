import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    access_token: str = ""
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"

    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    mistral_large_model: str = "mistral-large-latest"
    mistral_vision_model: str = "pixtral-large-latest"
    mistral_embed_model: str = "mistral-embed"
    mistral_monthly_budget_usd: float = 25.0
    mistral_base_url: str = "https://api.mistral.ai/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    whisper_model: str = "base"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def db_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return Path(url.removeprefix("sqlite:///"))
        return BASE_DIR / "data" / "app.db"

    @property
    def outbox_dir(self) -> Path:
        return BASE_DIR / "outbox"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.data_dir, 0o700)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.outbox_dir, 0o700)
        if self.db_path.parent != self.data_dir:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
