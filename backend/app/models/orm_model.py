from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


# =========================================================
# 1. 기준 테이블
# =========================================================

class Scenario(Base):
    __tablename__ = "scenario"

    scenario_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    weather_scenario = Column(String(50), nullable=False)
    risk_policy = Column(String(30))
    description = Column(Text)

    runs = relationship("SimulationRun", back_populates="scenario")


class GridCell(Base):
    __tablename__ = "grid_cell"

    cell_id = Column(BigInteger, primary_key=True, index=True)
    grid_x = Column(Integer, nullable=False)
    grid_y = Column(Integer, nullable=False)
    x_m = Column(Float)
    y_m = Column(Float)
    lon = Column(Float)
    lat = Column(Float)

    land_cover = Column(String(50))
    lc_code = Column(Integer)
    terrain_type = Column(String(50))

    road_distance = Column(Float)
    has_drivable_road = Column(Boolean, default=False)
    is_drivable = Column(Boolean, default=False)
    is_obstacle = Column(Boolean, default=False)

    mask_map_valid = Column(Boolean, default=True)
    mask_good = Column(Boolean, default=True)
    qa_b1_s1_n = Column(Float)
    qa_b2_s2_n = Column(Float)
    qa_b3_s2_invalid_pct = Column(Float)
    s2_valid_n_est = Column(Float)

    is_safe_zone = Column(Boolean, default=False)
    is_urban = Column(Boolean, default=False)
    is_wetland = Column(Boolean, default=False)
    comm_shadow_mountain = Column(Boolean, default=False)
    comm_shadow_urban = Column(Boolean, default=False)
    enemy_exposure_score = Column(Float, default=0)
    road_exposure_score = Column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("grid_x", "grid_y", name="uq_grid_cell_xy"),
        Index("idx_grid_cell_xy", "grid_x", "grid_y"),
        Index("idx_grid_cell_lonlat", "lon", "lat"),
    )


# =========================================================
# 2. 시뮬레이션 실행
# =========================================================

class SimulationRun(Base):
    __tablename__ = "simulation_run"

    run_id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenario.scenario_id", ondelete="RESTRICT"), nullable=False)
    start_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))

    mission_name = Column(String(120))
    mission_start_time = Column(DateTime)
    max_mission_time_min = Column(Integer)
    replan_cycle_min = Column(Integer, default=60)

    total_ugv_count = Column(Integer, nullable=False)
    total_operator_count = Column(Integer, nullable=False)
    unit_count = Column(Integer, nullable=False, default=3)

    status = Column(String(30), nullable=False, default="created")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("total_ugv_count >= 0", name="ck_run_total_ugv_count"),
        CheckConstraint("total_operator_count >= 0", name="ck_run_total_operator_count"),
        CheckConstraint("unit_count >= 1", name="ck_run_unit_count"),
        Index("idx_run_scenario", "scenario_id"),
    )

    scenario = relationship("Scenario", back_populates="runs")
    targets = relationship("MissionTarget", back_populates="run", cascade="all, delete-orphan")
    units = relationship("MissionUnit", back_populates="run", cascade="all, delete-orphan")
    goals = relationship("SimulationRunGoal", back_populates="run", cascade="all, delete-orphan")
    ugvs = relationship("UGV", back_populates="run", cascade="all, delete-orphan")
    operators = relationship("Operator", back_populates="run", cascade="all, delete-orphan")
    steps = relationship("SimulationStep", back_populates="run", cascade="all, delete-orphan")
    events = relationship("EventLog", back_populates="run", cascade="all, delete-orphan")
    run_summary = relationship("RunSummary", back_populates="run", uselist=False, cascade="all, delete-orphan")


class MissionTarget(Base):
    __tablename__ = "mission_target"

    target_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    target_order = Column(Integer, nullable=False)
    target_name = Column(String(100))
    target_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))
    lon = Column(Float)
    lat = Column(Float)
    reconnaissance_duration_min = Column(Integer)
    priority = Column(Integer, default=1)

    __table_args__ = (
        CheckConstraint("target_order >= 1", name="ck_target_order"),
        UniqueConstraint("run_id", "target_order", name="uq_target_run_order"),
        Index("idx_target_run", "run_id"),
    )

    run = relationship("SimulationRun", back_populates="targets")
    units = relationship("MissionUnit", back_populates="target")
    assignments = relationship("UnitAssignment", back_populates="target")


class MissionUnit(Base):
    __tablename__ = "mission_unit"

    unit_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_no = Column(Integer, nullable=False)
    unit_name = Column(String(50), nullable=False)
    target_id = Column(Integer, ForeignKey("mission_target.target_id", ondelete="SET NULL"))
    status = Column(String(30), default="planned")
    recommended_ratio = Column(String(20))

    __table_args__ = (
        CheckConstraint("unit_no >= 1", name="ck_unit_no"),
        UniqueConstraint("run_id", "unit_no", name="uq_unit_run_no"),
        Index("idx_unit_run", "run_id"),
    )

    run = relationship("SimulationRun", back_populates="units")
    target = relationship("MissionTarget", back_populates="units")
    assignments = relationship("UnitAssignment", back_populates="unit", cascade="all, delete-orphan")
    ugvs = relationship("UGV", back_populates="unit")
    operators = relationship("Operator", back_populates="unit")
    force_mix_candidates = relationship("ForceMixCandidate", back_populates="unit")
    status_snapshots = relationship("UnitStatusSnapshot", back_populates="unit")
    mission_risks = relationship("MissionRiskLayer", back_populates="unit")


class UnitAssignment(Base):
    __tablename__ = "unit_assignment"

    assignment_id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("mission_target.target_id", ondelete="SET NULL"))
    assigned_ugv_count = Column(Integer, nullable=False)
    assigned_operator_count = Column(Integer, nullable=False)
    assignment_label = Column(String(30))
    is_recommended = Column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint("assigned_ugv_count >= 0", name="ck_assignment_ugv_count"),
        CheckConstraint("assigned_operator_count >= 0", name="ck_assignment_operator_count"),
        Index("idx_assignment_unit", "unit_id"),
    )

    unit = relationship("MissionUnit", back_populates="assignments")
    target = relationship("MissionTarget", back_populates="assignments")


class SimulationRunGoal(Base):
    __tablename__ = "simulation_run_goal"

    goal_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    goal_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="RESTRICT"), nullable=False)
    goal_order = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("goal_order >= 1", name="ck_goal_order"),
        UniqueConstraint("run_id", "goal_order", name="uq_run_goal_order"),
    )

    run = relationship("SimulationRun", back_populates="goals")


# =========================================================
# 3. 기상 / 예측 / LTWR / 영향도 / 위험도
# =========================================================

class WeatherObserved(Base):
    __tablename__ = "weather_observed"

    obs_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)
    observed_time = Column(DateTime, nullable=False)
    rain_rate_mmph = Column(Float)
    visibility_index = Column(Float)
    soil_moisture = Column(Float)
    snow_depth = Column(Float)
    qom_grade = Column(String(20))

    __table_args__ = (
        UniqueConstraint("run_id", "cell_id", "observed_time", name="uq_weather_obs"),
        Index("idx_weather_obs_run_cell_time", "run_id", "cell_id", "observed_time"),
    )


class WeatherForecast(Base):
    __tablename__ = "weather_forecast"

    forecast_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)
    forecast_time = Column(DateTime, nullable=False)
    forecast_offset_hr = Column(Integer, nullable=False)
    rain_rate_mmph = Column(Float)
    visibility_index = Column(Float)
    soil_moisture = Column(Float)
    snow_depth = Column(Float)
    qom_grade = Column(String(20))
    uncertainty_score = Column(Float)

    __table_args__ = (
        CheckConstraint("forecast_offset_hr BETWEEN 0 AND 3", name="ck_weather_fcst_offset"),
        UniqueConstraint("run_id", "cell_id", "forecast_time", "forecast_offset_hr", name="uq_weather_fcst"),
        Index("idx_weather_fcst_run_cell_time", "run_id", "cell_id", "forecast_time", "forecast_offset_hr"),
    )


class LTWRAssessment(Base):
    __tablename__ = "ltwr_assessment"

    ltwr_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)
    forecast_time = Column(DateTime, nullable=False)
    forecast_offset_hr = Column(Integer, nullable=False)

    readiness_grade = Column(String(10), nullable=False)
    precipitation_score = Column(Float)
    visibility_score = Column(Float)
    soil_score = Column(Float)
    snow_score = Column(Float)
    impact_score = Column(Float)
    top1_driver = Column(String(50))
    top2_driver = Column(String(50))
    top3_driver = Column(String(50))
    qom_grade = Column(String(20))

    __table_args__ = (
        CheckConstraint("forecast_offset_hr BETWEEN 0 AND 3", name="ck_ltwr_offset"),
        UniqueConstraint("run_id", "cell_id", "forecast_time", "forecast_offset_hr", name="uq_ltwr"),
        Index("idx_ltwr_run_cell_time", "run_id", "cell_id", "forecast_time", "forecast_offset_hr"),
    )


class TacticalImpact(Base):
    __tablename__ = "tactical_impact"

    impact_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)
    forecast_time = Column(DateTime, nullable=False)
    forecast_offset_hr = Column(Integer, nullable=False)

    sensor_blackout_prob = Column(Float)
    speed_reduction = Column(Float)
    route_penalty = Column(Float)
    sos_risk = Column(Float)
    fallback_risk = Column(Float)
    queue_risk = Column(Float)
    intervention_time_multiplier = Column(Float)
    comm_risk = Column(Float)
    total_cost = Column(Float)

    __table_args__ = (
        CheckConstraint("forecast_offset_hr BETWEEN 0 AND 3", name="ck_tactical_offset"),
        UniqueConstraint("run_id", "cell_id", "forecast_time", "forecast_offset_hr", name="uq_tactical_impact"),
        Index("idx_tactical_run_cell_time", "run_id", "cell_id", "forecast_time", "forecast_offset_hr"),
    )


class MissionRiskLayer(Base):
    __tablename__ = "mission_risk_layer"

    mission_risk_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)
    forecast_time = Column(DateTime, nullable=False)
    forecast_offset_hr = Column(Integer, nullable=False)
    mission_type = Column(String(50), nullable=False)
    risk_score = Column(Float)
    risk_grade = Column(String(10))
    reason_summary = Column(Text)

    __table_args__ = (
        CheckConstraint("forecast_offset_hr BETWEEN 0 AND 3", name="ck_mission_risk_offset"),
        UniqueConstraint(
            "run_id",
            "unit_id",
            "cell_id",
            "forecast_time",
            "forecast_offset_hr",
            "mission_type",
            name="uq_mission_risk",
        ),
        Index("idx_risk_run_unit_time", "run_id", "unit_id", "forecast_time", "forecast_offset_hr"),
    )

    unit = relationship("MissionUnit", back_populates="mission_risks")


# =========================================================
# 4. 편성 후보 / 추천안
# =========================================================

class ForceMixCandidate(Base):
    __tablename__ = "force_mix_candidate"

    force_mix_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="CASCADE"))

    ugv_count = Column(Integer, nullable=False)
    operator_count = Column(Integer, nullable=False)

    simulation_rank = Column(Integer)
    risk_balance = Column(Float)
    mission_success_prob = Column(Float)
    estimated_loss_rate = Column(Float)
    operator_utilization = Column(Float)
    avg_wait_time = Column(Float)
    bottleneck_index = Column(Float)
    safety_margin = Column(Float)

    recommendation_reason = Column(Text)
    is_recommended = Column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint("ugv_count >= 0", name="ck_force_mix_ugv_count"),
        CheckConstraint("operator_count >= 0", name="ck_force_mix_operator_count"),
        Index("idx_force_mix_run_unit", "run_id", "unit_id"),
    )

    unit = relationship("MissionUnit", back_populates="force_mix_candidates")
    interventions = relationship("Intervention", back_populates="force_mix", cascade="all, delete-orphan")
    kpis = relationship("MissionKPI", back_populates="force_mix")
    recommendations = relationship("RecommendationLog", back_populates="recommended_force_mix")


class Intervention(Base):
    __tablename__ = "intervention"

    intervention_id = Column(BigInteger, primary_key=True, index=True)
    force_mix_id = Column(BigInteger, ForeignKey("force_mix_candidate.force_mix_id", ondelete="CASCADE"))
    driver_rank_id = Column(Integer)
    driver_type = Column(String(50))
    driver_label = Column(String(100))
    driver_score = Column(Float)

    force_mix = relationship("ForceMixCandidate", back_populates="interventions")


# =========================================================
# 5. 개체: UGV / Operator / Step
# =========================================================

class UGV(Base):
    __tablename__ = "ugv"

    ugv_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))

    ugv_label = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    current_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))

    base_speed_kmph = Column(Float)
    paved_speed_kmph = Column(Float)
    offroad_speed_kmph = Column(Float)

    battery_percent = Column(Float, default=100)
    sensor_ok = Column(Boolean, default=True)
    comms_ok = Column(Boolean, default=True)

    max_range_km = Column(Float)
    payload_kg = Column(Float)
    can_autonomous = Column(Boolean, default=True)
    can_manual = Column(Boolean, default=True)

    fallback_threshold_min = Column(Integer)
    destroy_threshold_min = Column(Integer)

    __table_args__ = (
        UniqueConstraint("run_id", "ugv_label", name="uq_ugv_run_label"),
        Index("idx_ugv_run_unit", "run_id", "unit_id"),
    )

    run = relationship("SimulationRun", back_populates="ugvs")
    unit = relationship("MissionUnit", back_populates="ugvs")
    state_logs = relationship("UGVStateLog", back_populates="ugv", cascade="all, delete-orphan")
    assignment_logs = relationship("OperatorAssignmentLog", back_populates="ugv")
    reservations = relationship("RouteCellReservation", back_populates="ugv")


class Operator(Base):
    __tablename__ = "operator"

    operator_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))

    operator_label = Column(String(30))
    status = Column(String(30))
    current_ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="SET NULL"))

    __table_args__ = (
        Index("idx_operator_run_unit", "run_id", "unit_id"),
    )

    run = relationship("SimulationRun", back_populates="operators")
    unit = relationship("MissionUnit", back_populates="operators")
    assignment_logs = relationship("OperatorAssignmentLog", back_populates="operator")


class SimulationStep(Base):
    __tablename__ = "simulation_step"

    step_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_time = Column(DateTime, nullable=False)
    forecast_offset_hr = Column(Integer)
    queue_length = Column(Integer, default=0)
    active_alert_count = Column(Integer, default=0)

    __table_args__ = (
        CheckConstraint(
            "(forecast_offset_hr IS NULL) OR (forecast_offset_hr BETWEEN 0 AND 3)",
            name="ck_step_offset"
        ),
        UniqueConstraint("run_id", "step_index", name="uq_simulation_step"),
        Index("idx_step_run_idx", "run_id", "step_index"),
    )

    run = relationship("SimulationRun", back_populates="steps")
    ugv_logs = relationship("UGVStateLog", back_populates="step")
    unit_snapshots = relationship("UnitStatusSnapshot", back_populates="step")
    alerts = relationship("AlertLog", back_populates="step")
    recommendations = relationship("RecommendationLog", back_populates="step")


# =========================================================
# 6. 경로
# =========================================================

class Path(Base):
    __tablename__ = "path"

    path_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    force_mix_id = Column(BigInteger, ForeignKey("force_mix_candidate.force_mix_id", ondelete="SET NULL"))
    ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="CASCADE"))

    route_kind = Column(String(20), nullable=False)  # initial / updated / alternative
    route_rank = Column(Integer, default=1)
    is_selected = Column(Boolean, default=False)

    start_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))
    goal_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))

    parent_path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="SET NULL"))
    trigger_event_id = Column(BigInteger)
    trigger_reason = Column(String(100))
    reason_summary = Column(Text)

    physical_cost = Column(Float)
    risk_cost = Column(Float)
    total_cost = Column(Float)
    eta_minutes = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "route_kind IN ('initial', 'updated', 'alternative')",
            name="ck_path_route_kind"
        ),
        Index("idx_path_run_unit_kind", "run_id", "unit_id", "route_kind"),
    )

    nodes = relationship("PathNode", back_populates="path", cascade="all, delete-orphan")
    reservations = relationship("RouteCellReservation", back_populates="path", cascade="all, delete-orphan")
    parent_path = relationship("Path", remote_side=[path_id])
    old_recommendations = relationship(
        "RecommendationLog",
        foreign_keys="RecommendationLog.old_path_id",
        back_populates="old_path"
    )
    new_recommendations = relationship(
        "RecommendationLog",
        foreign_keys="RecommendationLog.new_path_id",
        back_populates="new_path"
    )


class PathNode(Base):
    __tablename__ = "path_node"

    node_id = Column(BigInteger, primary_key=True, index=True)
    path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="CASCADE"), nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="RESTRICT"), nullable=False)
    order_index = Column(Integer, nullable=False)
    sim_time_index = Column(Integer)
    arrival_eta_min = Column(Float)

    __table_args__ = (
        UniqueConstraint("path_id", "order_index", name="uq_path_node_order"),
        Index("idx_path_node_path_order", "path_id", "order_index"),
    )

    path = relationship("Path", back_populates="nodes")


class RouteCellReservation(Base):
    __tablename__ = "route_cell_reservation"

    reservation_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="SET NULL"))
    sim_time_index = Column(Integer, nullable=False)
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "sim_time_index", "cell_id", name="uq_reservation_run_time_cell"),
        Index("idx_reservation_run_time_cell", "run_id", "sim_time_index", "cell_id"),
    )

    path = relationship("Path", back_populates="reservations")
    ugv = relationship("UGV", back_populates="reservations")


# =========================================================
# 7. 상태 / 로그 / KPI / 알림
# =========================================================

class MissionKPI(Base):
    __tablename__ = "mission_kpi"

    kpi_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    force_mix_id = Column(BigInteger, ForeignKey("force_mix_candidate.force_mix_id", ondelete="CASCADE"))
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="SET NULL"))

    mission_completion_rate = Column(Float)
    survival_rate = Column(Float)
    estimated_loss_rate = Column(Float)
    avg_wait_time = Column(Float)
    operator_utilization = Column(Float)
    bottleneck_index = Column(Float)
    tail_risk = Column(Float)
    safety_margin = Column(Float)

    __table_args__ = (
        Index("idx_kpi_run_unit", "run_id", "unit_id"),
    )

    force_mix = relationship("ForceMixCandidate", back_populates="kpis")


class RunSummary(Base):
    __tablename__ = "run_summary"

    summary_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False, unique=True)
    overall_success_prob = Column(Float)
    estimated_loss_rate = Column(Float)
    manpower_saved = Column(Integer)
    remaining_time_min = Column(Float)
    current_phase = Column(String(30))
    recommended_force_mix = Column(String(50))
    reroute_recommended = Column(Boolean, default=False)
    latest_reason_summary = Column(Text)

    run = relationship("SimulationRun", back_populates="run_summary")


class UnitStatusSnapshot(Base):
    __tablename__ = "unit_status_snapshot"

    snapshot_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="CASCADE"))
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="CASCADE"), nullable=False)

    current_path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="SET NULL"))
    updated_path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="SET NULL"))

    assigned_ugv_count = Column(Integer)
    sos_count = Column(Integer, default=0)
    queue_length = Column(Integer, default=0)
    eta_minutes = Column(Float)
    mission_success_prob = Column(Float)
    estimated_loss_rate = Column(Float)
    ltwr_grade = Column(String(10))

    current_status = Column(String(30))
    card_reason_summary = Column(Text)

    __table_args__ = (
        Index("idx_snapshot_run_step_unit", "run_id", "step_id", "unit_id"),
    )

    step = relationship("SimulationStep", back_populates="unit_snapshots")
    unit = relationship("MissionUnit", back_populates="status_snapshots")


class UGVStateLog(Base):
    __tablename__ = "ugv_state_log"

    log_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="CASCADE"), nullable=False)
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="SET NULL"))

    current_cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))
    is_sos = Column(Boolean, default=False)
    status = Column(String(30))
    applied_speed_kmph = Column(Float)
    remaining_time_min = Column(Float)
    wait_time_min = Column(Float)
    neglect_time_min = Column(Float)
    mode = Column(String(30))
    forecast_offset_hr = Column(Integer)

    __table_args__ = (
        CheckConstraint(
            "(forecast_offset_hr IS NULL) OR (forecast_offset_hr BETWEEN 0 AND 3)",
            name="ck_ugv_log_offset"
        ),
        Index("idx_ugv_log_run_ugv_step", "run_id", "ugv_id", "step_id"),
    )

    ugv = relationship("UGV", back_populates="state_logs")
    step = relationship("SimulationStep", back_populates="ugv_logs")


class EventLog(Base):
    __tablename__ = "event_log"

    event_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="SET NULL"))
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="SET NULL"))

    event_type = Column(String(50), nullable=False)
    severity = Column(String(20))
    event_time = Column(DateTime, nullable=False)
    resolved_time = Column(DateTime)
    is_active = Column(Boolean, default=True)
    message = Column(Text)

    __table_args__ = (
        Index("idx_event_run_time", "run_id", "event_time"),
    )

    run = relationship("SimulationRun", back_populates="events")
    assignment_logs = relationship("OperatorAssignmentLog", back_populates="event")


class OperatorAssignmentLog(Base):
    __tablename__ = "operator_assignment_log"

    assignment_id = Column(BigInteger, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("operator.operator_id", ondelete="CASCADE"), nullable=False)
    ugv_id = Column(Integer, ForeignKey("ugv.ugv_id", ondelete="CASCADE"), nullable=False)
    event_id = Column(BigInteger, ForeignKey("event_log.event_id", ondelete="SET NULL"))
    assigned_time = Column(DateTime)
    released_time = Column(DateTime)
    assign_status = Column(String(30))

    operator = relationship("Operator", back_populates="assignment_logs")
    ugv = relationship("UGV", back_populates="assignment_logs")
    event = relationship("EventLog", back_populates="assignment_logs")


class AlertLog(Base):
    __tablename__ = "alert_log"

    alert_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="SET NULL"))
    cell_id = Column(BigInteger, ForeignKey("grid_cell.cell_id", ondelete="SET NULL"))

    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20))
    title = Column(String(120))
    message = Column(Text)
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_alert_run_step", "run_id", "step_id"),
    )

    step = relationship("SimulationStep", back_populates="alerts")


class RecommendationLog(Base):
    __tablename__ = "recommendation_log"

    recommendation_id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_run.run_id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("mission_unit.unit_id", ondelete="SET NULL"))
    step_id = Column(BigInteger, ForeignKey("simulation_step.step_id", ondelete="SET NULL"))

    recommendation_type = Column(String(50), nullable=False)
    title = Column(String(120))
    reason_summary = Column(Text)
    old_path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="SET NULL"))
    new_path_id = Column(BigInteger, ForeignKey("path.path_id", ondelete="SET NULL"))
    recommended_force_mix_id = Column(BigInteger, ForeignKey("force_mix_candidate.force_mix_id", ondelete="SET NULL"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_reco_run_step", "run_id", "step_id"),
    )

    step = relationship("SimulationStep", back_populates="recommendations")
    old_path = relationship("Path", foreign_keys=[old_path_id], back_populates="old_recommendations")
    new_path = relationship("Path", foreign_keys=[new_path_id], back_populates="new_recommendations")
    recommended_force_mix = relationship("ForceMixCandidate", back_populates="recommendations")