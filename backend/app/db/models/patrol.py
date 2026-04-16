"""
backend/app/db/models/patrol.py

run_patrol_events 테이블 ORM 모델.

UGV가 목적지에 도착하면 patrol 이벤트가 생성되고,
arrived_at 기준으로 patrol_duration_sec 카운트다운이 시작된다.
completed_at이 NULL이면 현재 정찰 중.
"""

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunPatrolEvent(Base):
    __tablename__ = "run_patrol_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_no: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    target_seq: Mapped[int] = mapped_column(Integer, nullable=False)  # 목적지 순번 (1, 2, 3)
    target_lat: Mapped[float] = mapped_column(Double, nullable=False)
    target_lon: Mapped[float] = mapped_column(Double, nullable=False)
    patrol_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    # mission_targets.patrol_duration_sec 에서 복사. 카운트다운 총 시간.
    arrived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 도착 시각 = 카운트다운 시작 기준점
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NULL = 정찰 중 / 값 있음 = 정찰 완료
