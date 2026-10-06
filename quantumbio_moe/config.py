from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    LOCALMOE_LOG_LEVEL: str = "INFO"
    MODEL_DIRECTORY: str = "./models"
    MODEL_EXTRA_DIRECTORIES: str = ""
    MODEL_NAME: str = ""
    DRAFT_MODEL_PATH: str = ""
    QUANTIZATION_TYPE: str = "AWQ"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:secret@localhost:5432/localmoe"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DRAFT_MODEL_PATH: str = ""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_NAME: str = "quantumbio-moe-local"
    API_TIMEOUT_SECONDS: int = 300
    AUTO_CONNECT_INFRA: bool = True
    INFRA_CONNECT_TIMEOUT: int = 3

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"


settings = Settings()