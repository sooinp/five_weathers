"""
backend/app/db/base.py

SQLAlchemy DeclarativeBase 정의.
모든 ORM 모델이 이 Base를 상속.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
