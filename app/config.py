from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:////tmp/readiness.db"
    log_level: str = "INFO"
    port: int = 8000


settings = Settings()
