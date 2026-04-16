"""
backend/app/db/models/alert.py

run_alerts 테이블 ORM 모델.
심각도: INFO | WARN | ERROR
유형: REROUTE | SOS | SENSOR_LOSS | QUEUE_OVERFLOW | MISSION_FAIL 등
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RunAlert(Base):
    __tablename__ = "run_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    # INFO | WARN | ERROR
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["SimulationRun"] = relationship(  # noqa: F821
        "SimulationRun", back_populates="alerts"
    )
