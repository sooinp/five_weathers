"""
backend/app/core/logging.py

애플리케이션 전역 로거 설정.
uvicorn 로그와 통합되도록 핸들러를 공유.
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """main.py startup 이벤트에서 호출."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # 외부 라이브러리 노이즈 줄이기
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
