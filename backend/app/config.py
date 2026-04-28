from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SismoBot API"

    LM_STUDIO_BASE_URL: str = "http://host.docker.internal:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"
    LM_STUDIO_MODEL: str = "mistralai/ministral-3-14b-reasoning"

    class Config:
        env_file = ".env"


settings = Settings()
