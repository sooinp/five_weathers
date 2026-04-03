## 설정, 공통 로직
## Application settings

import os

class Settings:
    app_name: str = os.getenv("APP_NAME", "FiveWeather Backend")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/fiveweathers",
    )

settings = Settings()
