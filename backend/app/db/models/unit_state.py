"""
backend/app/db/models/unit_state.py

run_units / run_queue_events / run_sos_events 테이블 ORM 모델.

run_units:
    - 각 UGV 유닛의 현재 상태 (위치, 상태코드, 메시지)
    - run_id + unit_no 기준으로 UPSERT

run_queue_events:
    - 대기열 진입/이탈 이벤트 기록 (QUEUED 기반)

run_sos_events:
    - SOS 요청 발생/해제 이벤트 기록
    - SOS 발생 시각이 대기열 카운트업 시작점
    - FIFO 처리 순서는 sos_at (발생 시각) 오름차순
"""

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunUnit(Base):
    __tablename__ = "run_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_no: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="STANDBY")
    # STANDBY | MOVING | QUEUED | SOS | DONE
    lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    lon: Mapped[float | None] = mapped_column(Double, nullable=True)
    message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run: Mapped["SimulationRun"] = relationship(  # noqa: F821
        "SimulationRun", back_populates="units"
    )


class RunQueueEvent(Base):
    __tablename__ = "run_queue_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    wait_time_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # ENTER | EXIT | PRIORITY_CHANGE
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["SimulationRun"] = relationship(  # noqa: F821
        "SimulationRun", back_populates="queue_events"
    )


class RunSosEvent(Base):
    __tablename__ = "run_sos_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_no: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # SOS        : SOS 요청 발생 → 대기열 카운트업 시작
    # SOS_RESOLVED: SOS 해제 → 대기열에서 제거 (일대일 처리 완료)
    sos_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # SOS 발생 시각 = 카운트업 기준점 (FIFO 정렬 기준)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NULL = 아직 대기 중 / 값 있음 = 처리 완료 (일대일 대응)
    lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    lon: Mapped[float | None] = mapped_column(Double, nullable=True)

    run: Mapped["SimulationRun"] = relationship(  # noqa: F821
        "SimulationRun", back_populates="sos_events"
    )
