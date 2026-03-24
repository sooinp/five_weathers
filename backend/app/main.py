## FastAPI 서버 시작점
## api 폴더가 API 라우터

from fastapi import FastAPI
from app.api import simulation

app = FastAPI()

app.include_router(simulation.router)