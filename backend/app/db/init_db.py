"""
backend/app/db/init_db.py

서버 startup 시 테이블 생성 + 기본 admin 계정 시드.

주의: 프로덕션에서는 Alembic migration으로 스키마 관리.
      이 파일은 개발 초기 빠른 부팅용.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import engine

logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """모든 테이블 CREATE TABLE IF NOT EXISTS."""
    # models/__init__.py 임포트로 Base.metadata에 등록
    import app.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB tables created (if not exist)")

## 지휘관 계정 생성
async def seed_admin(session: AsyncSession) -> None:
    """admin 계정이 없으면 생성."""
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD not set — skipping admin seed")
        return

    logger.info("seed_admin: username=%r  password_len=%d",
                settings.admin_username, len(settings.admin_password))

    result = await session.execute(
        select(User).where(User.username == settings.admin_username)
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Admin user already exists: %s", settings.admin_username)
        return

    admin = User(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        role="commander",
    )
    session.add(admin)
    await session.commit()
    logger.info("Admin user '%s' created", settings.admin_username)

## 통제관(3제대까지) 계정 생성
async def seed_operator(
    session: AsyncSession,
    username: str,
    password: str,
    assigned_unit: str | None = None,
) -> None:
    """operator 계정이 없으면 생성."""
    if not password:
        logger.warning("Operator password missing for username=%s — skipping", username)
        return

    result = await session.execute(
        select(User).where(User.username == username)
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Operator user already exists: %s", username)
        return

    operator = User(
        username=username,
        password_hash=hash_password(password),
        role="operator",
        assigned_unit=assigned_unit,
    )
    session.add(operator)
    await session.commit()
    logger.info("Operator user '%s' created (unit=%s)", username, assigned_unit)


async def seed_default_operators(session: AsyncSession) -> None:
    """기본 통제관 계정들 생성."""
    default_operators = [
        {"username": "user1", "password": "user1", "assigned_unit": "1제대"},
        {"username": "user2", "password": "user2", "assigned_unit": "2제대"},
        {"username": "user3", "password": "user3", "assigned_unit": "3제대"},
    ]

    for op in default_operators:
        await seed_operator(
            session=session,
            username=op["username"],
            password=op["password"],
            assigned_unit=op["assigned_unit"],
        )


async def init_db() -> None:
    """테이블 생성 후 기본 계정 시드."""
    await create_tables()

    async with AsyncSession(engine) as session:
        await seed_admin(session)
        await seed_default_operators(session)