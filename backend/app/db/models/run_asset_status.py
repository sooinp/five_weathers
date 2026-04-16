"""
backend/app/db/models/run_asset_status.py

run_asset_statuses 테이블 ORM 모델.

목적:
  - PDF 6, 10페이지의 자산 현황 편집값 저장
  - run 단위로 스냅샷 입력값 보관 (제대별)
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunAssetStatus(Base):
    __tablename__ = "run_asset_statuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )  # 마지막으로 수정한 사용자

    unit_scope: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 1, 2, 3 제대 / operator는 본인 제대

    troop_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_ugv_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    departure_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 관계
    run: Mapped["SimulationRun"] = relationship(  # noqa: F821
        "SimulationRun", back_populates="asset_statuses"
    )
