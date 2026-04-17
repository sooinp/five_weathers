"""
backend/reset_admin_pwd.py

startup seed가 실패했을 때 admin 계정을 직접 생성/복구하는 스크립트.

실행:
    (backend 폴더에서)
    python create_admin.py
    python create_admin.py --username user1 --password user1
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.init_db import create_tables
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


async def upsert_admin(username: str, password: str, role: str = "commander") -> None:
    await create_tables()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        pw_hash = hash_password(password)

        if user:
            user.password_hash = pw_hash
            user.role = role
            print(f"[OK] '{username}' 계정 비밀번호/역할 업데이트 완료")
        else:
            db.add(User(username=username, password_hash=pw_hash, role=role))
            print(f"[OK] '{username}' 계정 새로 생성 완료")

        await db.commit()

    print(f"     → 아이디: {username} / 비밀번호: {password}")


def main():
    parser = argparse.ArgumentParser(description="Admin 계정 생성/복구")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--role",     default="commander")
    args = parser.parse_args()

    try:
        asyncio.run(upsert_admin(args.username, args.password, args.role))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
