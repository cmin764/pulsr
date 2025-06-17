from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Pulsr - ML Pipeline Orchestration API"
    version: str = "0.1.0"
    debug: bool = False

    # Database settings
    database_url: str = "sqlite:///./pulsr.db"

    # API settings
    api_v1_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"


settings = Settings()
