from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    upload_url: str
    upload_x_api_key: str
    upload_timeout_seconds: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()