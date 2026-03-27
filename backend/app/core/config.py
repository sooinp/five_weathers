
"""Application settings."""

import os


class Settings:
    app_name: str = os.getenv("APP_NAME", "FiveWeather Backend")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/fiveweather",
    )


settings = Settings()
