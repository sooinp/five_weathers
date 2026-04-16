"""
backend/app/core/rate_limit.py

Brute-force / Rate Limiting 방어.

두 레이어로 구성:
  1. slowapi — IP당 엔드포인트별 요청 횟수 제한 (sliding window)
  2. LoginGuard — 연속 로그인 실패 시 IP 잠금 (인메모리)

LoginGuard 정책:
  - 5회 연속 실패 → 15분 잠금
  - 잠금 중 추가 요청 → 즉시 429
  - 성공 시 카운터 초기화
"""

import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ── slowapi 전역 limiter ──────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Brute-force 잠금 (인메모리) ───────────────────────────

_MAX_FAILURES   = 5          # 연속 실패 허용 횟수
_LOCKOUT_SEC    = 60 * 15    # 잠금 시간 (초)

_lock = Lock()
_failures: dict[str, int]   = defaultdict(int)   # ip → 연속 실패 횟수
_locked_until: dict[str, float] = {}              # ip → 잠금 해제 시각(epoch)


class LoginGuard:
    """로그인 엔드포인트에서 사용하는 brute-force 방어 헬퍼."""

    @staticmethod
    def check(request: Request) -> None:
        """잠금 상태면 429 발생."""
        ip = get_remote_address(request)
        with _lock:
            until = _locked_until.get(ip, 0)
            if until > time.time():
                remaining = int(until - time.time())
                logger.warning("Blocked login attempt from %s (%ds remaining)", ip, remaining)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"너무 많은 로그인 시도입니다. {remaining}초 후 다시 시도하세요.",
                    headers={"Retry-After": str(remaining)},
                )

    @staticmethod
    def on_failure(request: Request) -> None:
        """실패 카운터 증가, 임계치 초과 시 잠금."""
        ip = get_remote_address(request)
        with _lock:
            _failures[ip] += 1
            if _failures[ip] >= _MAX_FAILURES:
                _locked_until[ip] = time.time() + _LOCKOUT_SEC
                logger.warning(
                    "IP %s locked out after %d failures (%ds)",
                    ip, _failures[ip], _LOCKOUT_SEC,
                )

    @staticmethod
    def on_success(request: Request) -> None:
        """로그인 성공 시 카운터 초기화."""
        ip = get_remote_address(request)
        with _lock:
            _failures.pop(ip, None)
            _locked_until.pop(ip, None)
