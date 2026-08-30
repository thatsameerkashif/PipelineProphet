from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    APP_NAME: str = "Demo App"

    class Config:
        env_file = ".env"


settings = Settings()
