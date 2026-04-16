"""
backend/app/db/models/simulation_run.py

simulation_runs 테이블 ORM 모델.

run_id 중심으로 모든 실행 결과가 연결되는 핵심 테이블.
status: CREATED → RUNNING → COMPLETED | FAILED | CANCELLED
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CREATED"
    )  # CREATED | RUNNING | COMPLETED | FAILED | CANCELLED
    phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # INIT | PATHFINDING | EXECUTION | REPLAN | DONE
    selected_mode: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="balanced"
    )
    # 임무 모드: balanced(균형) | recon(정찰) | rapid(신속)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 관계
    mission: Mapped["Mission"] = relationship("Mission", back_populates="runs")  # noqa: F821
    snapshots: Mapped[list["RunStatusSnapshot"]] = relationship(  # noqa: F821
        "RunStatusSnapshot", back_populates="run", cascade="all, delete-orphan"
    )
    panels: Mapped[list["RunTimeSeriesPanel"]] = relationship(  # noqa: F821
        "RunTimeSeriesPanel", back_populates="run", cascade="all, delete-orphan"
    )
    units: Mapped[list["RunUnit"]] = relationship(  # noqa: F821
        "RunUnit", back_populates="run", cascade="all, delete-orphan"
    )
    queue_events: Mapped[list["RunQueueEvent"]] = relationship(  # noqa: F821
        "RunQueueEvent", back_populates="run", cascade="all, delete-orphan"
    )
    sos_events: Mapped[list["RunSosEvent"]] = relationship(  # noqa: F821
        "RunSosEvent", back_populates="run", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["RunAlert"]] = relationship(  # noqa: F821
        "RunAlert", back_populates="run", cascade="all, delete-orphan"
    )
    routes: Mapped[list["RunRoute"]] = relationship(  # noqa: F821
        "RunRoute", back_populates="run", cascade="all, delete-orphan"
    )
    map_layers: Mapped[list["RunMapLayer"]] = relationship(  # noqa: F821
        "RunMapLayer", back_populates="run", cascade="all, delete-orphan"
    )
    kpis: Mapped[list["RunKpi"]] = relationship(  # noqa: F821
        "RunKpi", back_populates="run", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["RunRecommendation"]] = relationship(  # noqa: F821
        "RunRecommendation", back_populates="run", cascade="all, delete-orphan"
    )
    route_effects: Mapped[list["RunRouteEffect"]] = relationship(  # noqa: F821
        "RunRouteEffect", back_populates="run", cascade="all, delete-orphan"
    )
    input_assets: Mapped[list["RunInputAsset"]] = relationship(  # noqa: F821
        "RunInputAsset", cascade="all, delete-orphan"
    )
    asset_statuses: Mapped[list["RunAssetStatus"]] = relationship(  # noqa: F821
        "RunAssetStatus", back_populates="run", cascade="all, delete-orphan"
    )
