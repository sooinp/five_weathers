"""
인증 통합 패치 가이드
=====================
아래 코드를 기존 파일에 적용하세요.

실제 파일 위치:
  app/config.py          — 설정 필드 추가
  app/main.py            — auth 라우터 등록
  app/api/simulation.py  — API Key 의존성 적용
"""

# ══════════════════════════════════════════════
# [1] app/config.py — 설정 필드 추가
# ══════════════════════════════════════════════
#
# 기존 Settings 클래스에 아래 필드를 추가하세요:
#
# class Settings(BaseSettings):
#     database_url: str
#     tif_storage_path: str = "./data/tif"
#
#     # ── 아래 3줄 추가 ──────────────────────
#     ml_api_key: str = ""
#     jwt_secret_key: str = ""
#     jwt_algorithm: str = "HS256"
#     jwt_access_token_expire_minutes: int = 60
#     admin_username: str = "admin"
#     admin_password: str = ""
#
# .env에 추가할 항목:
#   ML_API_KEY=ml-secret-key-change-me
#   JWT_SECRET_KEY=jwt-secret-key-change-me
#   ADMIN_USERNAME=admin
#   ADMIN_PASSWORD=admin-password-change-me


# ══════════════════════════════════════════════
# [2] app/main.py — auth 라우터 등록
# ══════════════════════════════════════════════
#
# 기존 라우터 include 블록에 아래를 추가:
#
# from app.api import auth  # ← 추가
#
# app.include_router(auth.router)  # ← 추가 (다른 include_router 옆에)


# ══════════════════════════════════════════════
# [3] app/api/simulation.py — API Key 적용
# ══════════════════════════════════════════════
#
# 파일 상단 임포트에 추가:
#   from app.security import RequireApiKey
#
# POST /api/simulation/result 엔드포인트 시그니처 변경:
#
# 변경 전:
#   @router.post("/result")
#   async def receive_simulation_result(
#       ...기존 파라미터들...
#   ):
#
# 변경 후:
#   @router.post("/result")
#   async def receive_simulation_result(
#       _: RequireApiKey,          # ← 이 한 줄만 추가
#       ...기존 파라미터들...
#   ):
#
# POST /api/simulation/start, /api/simulation/stop 도 동일하게 적용 권장.


# ══════════════════════════════════════════════
# [4] .env 예시 (전체)
# ══════════════════════════════════════════════
ENV_EXAMPLE = """
# DB
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/hanhwa

# 파일 저장
TIF_STORAGE_PATH=./data/tif

# ML 서버 인증 (POST /api/simulation/* 엔드포인트)
ML_API_KEY=ml-secret-key-change-me

# JWT (프론트엔드 로그인, 추후 활성화)
JWT_SECRET_KEY=jwt-secret-key-change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# 관리자 계정 (JWT 로그인용)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin-password-change-me
"""
