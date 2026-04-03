-- =========================================================
-- DROP ORDER
-- =========================================================
DROP TABLE IF EXISTS route_cell_reservation CASCADE;
DROP TABLE IF EXISTS recommendation_log CASCADE;
DROP TABLE IF EXISTS alert_log CASCADE;
DROP TABLE IF EXISTS unit_status_snapshot CASCADE;
DROP TABLE IF EXISTS run_summary CASCADE;
DROP TABLE IF EXISTS operator_assignment_log CASCADE;
DROP TABLE IF EXISTS event_log CASCADE;
DROP TABLE IF EXISTS ugv_state_log CASCADE;
DROP TABLE IF EXISTS mission_kpi CASCADE;
DROP TABLE IF EXISTS intervention CASCADE;
DROP TABLE IF EXISTS path_node CASCADE;
DROP TABLE IF EXISTS path CASCADE;
DROP TABLE IF EXISTS simulation_step CASCADE;
DROP TABLE IF EXISTS operator CASCADE;
DROP TABLE IF EXISTS ugv CASCADE;
DROP TABLE IF EXISTS force_mix_candidate CASCADE;
DROP TABLE IF EXISTS mission_risk_layer CASCADE;
DROP TABLE IF EXISTS tactical_impact CASCADE;
DROP TABLE IF EXISTS ltwr_assessment CASCADE;
DROP TABLE IF EXISTS weather_forecast CASCADE;
DROP TABLE IF EXISTS weather_observed CASCADE;
DROP TABLE IF EXISTS unit_assignment CASCADE;
DROP TABLE IF EXISTS mission_unit CASCADE;
DROP TABLE IF EXISTS mission_target CASCADE;
DROP TABLE IF EXISTS simulation_run_goal CASCADE;
DROP TABLE IF EXISTS simulation_run CASCADE;
DROP TABLE IF EXISTS grid_cell CASCADE;
DROP TABLE IF EXISTS scenario CASCADE;

-- =========================================================
-- 1. 기준 테이블
-- =========================================================
CREATE TABLE scenario (
    scenario_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    weather_scenario VARCHAR(50) NOT NULL,
    risk_policy VARCHAR(30),
    description TEXT
);

CREATE TABLE grid_cell (
    cell_id BIGINT PRIMARY KEY,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    x_m DOUBLE PRECISION,
    y_m DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,

    land_cover VARCHAR(50),
    lc_code INTEGER,
    terrain_type VARCHAR(50),

    road_distance DOUBLE PRECISION,
    has_drivable_road BOOLEAN DEFAULT FALSE,
    is_drivable BOOLEAN DEFAULT FALSE,
    is_obstacle BOOLEAN DEFAULT FALSE,

    mask_map_valid BOOLEAN DEFAULT TRUE,
    mask_good BOOLEAN DEFAULT TRUE,
    qa_b1_s1_n DOUBLE PRECISION,
    qa_b2_s2_n DOUBLE PRECISION,
    qa_b3_s2_invalid_pct DOUBLE PRECISION,
    s2_valid_n_est DOUBLE PRECISION,

    is_safe_zone BOOLEAN DEFAULT FALSE,
    is_urban BOOLEAN DEFAULT FALSE,
    is_wetland BOOLEAN DEFAULT FALSE,
    comm_shadow_mountain BOOLEAN DEFAULT FALSE,
    comm_shadow_urban BOOLEAN DEFAULT FALSE,
    enemy_exposure_score DOUBLE PRECISION DEFAULT 0,
    road_exposure_score DOUBLE PRECISION DEFAULT 0,

    UNIQUE (grid_x, grid_y)
);

-- =========================================================
-- 2. 시뮬레이션 실행
-- =========================================================
CREATE TABLE simulation_run (
    run_id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES scenario(scenario_id) ON DELETE RESTRICT,
    start_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,

    mission_name VARCHAR(120),
    mission_start_time TIMESTAMP,
    max_mission_time_min INTEGER,
    replan_cycle_min INTEGER DEFAULT 60,

    total_ugv_count INTEGER NOT NULL CHECK (total_ugv_count >= 0),
    total_operator_count INTEGER NOT NULL CHECK (total_operator_count >= 0),
    unit_count INTEGER NOT NULL DEFAULT 3 CHECK (unit_count >= 1),

    status VARCHAR(30) NOT NULL DEFAULT 'created',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE mission_target (
    target_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    target_order INTEGER NOT NULL CHECK (target_order >= 1),
    target_name VARCHAR(100),
    target_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    reconnaissance_duration_min INTEGER,
    priority INTEGER DEFAULT 1,
    UNIQUE (run_id, target_order)
);

CREATE TABLE mission_unit (
    unit_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_no INTEGER NOT NULL CHECK (unit_no >= 1),
    unit_name VARCHAR(50) NOT NULL,
    target_id INTEGER REFERENCES mission_target(target_id) ON DELETE SET NULL,
    status VARCHAR(30) DEFAULT 'planned',
    recommended_ratio VARCHAR(20),
    UNIQUE (run_id, unit_no)
);

CREATE TABLE unit_assignment (
    assignment_id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL REFERENCES mission_unit(unit_id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES mission_target(target_id) ON DELETE SET NULL,
    assigned_ugv_count INTEGER NOT NULL CHECK (assigned_ugv_count >= 0),
    assigned_operator_count INTEGER NOT NULL CHECK (assigned_operator_count >= 0),
    assignment_label VARCHAR(30),
    is_recommended BOOLEAN DEFAULT FALSE
);

CREATE TABLE simulation_run_goal (
    goal_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    goal_cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE RESTRICT,
    goal_order INTEGER NOT NULL CHECK (goal_order >= 1),
    UNIQUE (run_id, goal_order)
);

-- =========================================================
-- 3. 기상 / 예측 / LTWR / 영향도 / 위험도
-- =========================================================
CREATE TABLE weather_observed (
    obs_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    observed_time TIMESTAMP NOT NULL,
    rain_rate_mmph DOUBLE PRECISION,
    visibility_index DOUBLE PRECISION,
    soil_moisture DOUBLE PRECISION,
    snow_depth DOUBLE PRECISION,
    qom_grade VARCHAR(20),
    UNIQUE (run_id, cell_id, observed_time)
);

CREATE TABLE weather_forecast (
    forecast_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    forecast_time TIMESTAMP NOT NULL,
    forecast_offset_hr INTEGER NOT NULL CHECK (forecast_offset_hr BETWEEN 0 AND 3),
    rain_rate_mmph DOUBLE PRECISION,
    visibility_index DOUBLE PRECISION,
    soil_moisture DOUBLE PRECISION,
    snow_depth DOUBLE PRECISION,
    qom_grade VARCHAR(20),
    uncertainty_score DOUBLE PRECISION,
    UNIQUE (run_id, cell_id, forecast_time, forecast_offset_hr)
);

CREATE TABLE ltwr_assessment (
    ltwr_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    forecast_time TIMESTAMP NOT NULL,
    forecast_offset_hr INTEGER NOT NULL CHECK (forecast_offset_hr BETWEEN 0 AND 3),
    readiness_grade VARCHAR(10) NOT NULL,
    precipitation_score DOUBLE PRECISION,
    visibility_score DOUBLE PRECISION,
    soil_score DOUBLE PRECISION,
    snow_score DOUBLE PRECISION,
    impact_score DOUBLE PRECISION,
    top1_driver VARCHAR(50),
    top2_driver VARCHAR(50),
    top3_driver VARCHAR(50),
    qom_grade VARCHAR(20),
    UNIQUE (run_id, cell_id, forecast_time, forecast_offset_hr)
);

CREATE TABLE tactical_impact (
    impact_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    forecast_time TIMESTAMP NOT NULL,
    forecast_offset_hr INTEGER NOT NULL CHECK (forecast_offset_hr BETWEEN 0 AND 3),

    sensor_blackout_prob DOUBLE PRECISION,
    speed_reduction DOUBLE PRECISION,
    route_penalty DOUBLE PRECISION,
    sos_risk DOUBLE PRECISION,
    fallback_risk DOUBLE PRECISION,
    queue_risk DOUBLE PRECISION,
    intervention_time_multiplier DOUBLE PRECISION,
    comm_risk DOUBLE PRECISION,
    total_cost DOUBLE PRECISION,

    UNIQUE (run_id, cell_id, forecast_time, forecast_offset_hr)
);

CREATE TABLE mission_risk_layer (
    mission_risk_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    forecast_time TIMESTAMP NOT NULL,
    forecast_offset_hr INTEGER NOT NULL CHECK (forecast_offset_hr BETWEEN 0 AND 3),
    mission_type VARCHAR(50) NOT NULL,
    risk_score DOUBLE PRECISION,
    risk_grade VARCHAR(10),
    reason_summary TEXT,
    UNIQUE (run_id, unit_id, cell_id, forecast_time, forecast_offset_hr, mission_type)
);

-- =========================================================
-- 4. 편제 후보 / 추천안
-- =========================================================
CREATE TABLE force_mix_candidate (
    force_mix_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE CASCADE,

    ugv_count INTEGER NOT NULL CHECK (ugv_count >= 0),
    operator_count INTEGER NOT NULL CHECK (operator_count >= 0),

    simulation_rank INTEGER,
    risk_balance DOUBLE PRECISION,
    mission_success_prob DOUBLE PRECISION,
    estimated_loss_rate DOUBLE PRECISION,
    operator_utilization DOUBLE PRECISION,
    avg_wait_time DOUBLE PRECISION,
    bottleneck_index DOUBLE PRECISION,
    safety_margin DOUBLE PRECISION,

    recommendation_reason TEXT,
    is_recommended BOOLEAN DEFAULT FALSE
);

CREATE TABLE intervention (
    intervention_id BIGSERIAL PRIMARY KEY,
    force_mix_id BIGINT REFERENCES force_mix_candidate(force_mix_id) ON DELETE CASCADE,
    driver_rank_id INTEGER,
    driver_type VARCHAR(50),
    driver_label VARCHAR(100),
    driver_score DOUBLE PRECISION
);

-- =========================================================
-- 5. 개체: UGV / Operator / Step
-- =========================================================
CREATE TABLE ugv (
    ugv_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,

    ugv_label VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    current_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,

    base_speed_kmph DOUBLE PRECISION,
    paved_speed_kmph DOUBLE PRECISION,
    offroad_speed_kmph DOUBLE PRECISION,

    battery_percent DOUBLE PRECISION DEFAULT 100,
    sensor_ok BOOLEAN DEFAULT TRUE,
    comms_ok BOOLEAN DEFAULT TRUE,

    max_range_km DOUBLE PRECISION,
    payload_kg DOUBLE PRECISION,
    can_autonomous BOOLEAN DEFAULT TRUE,
    can_manual BOOLEAN DEFAULT TRUE,

    fallback_threshold_min INTEGER,
    destroy_threshold_min INTEGER,

    UNIQUE (run_id, ugv_label)
);

CREATE TABLE operator (
    operator_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,

    operator_label VARCHAR(30),
    status VARCHAR(30),
    current_ugv_id INTEGER REFERENCES ugv(ugv_id) ON DELETE SET NULL
);

CREATE TABLE simulation_step (
    step_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    step_time TIMESTAMP NOT NULL,
    forecast_offset_hr INTEGER CHECK (forecast_offset_hr BETWEEN 0 AND 3),
    queue_length INTEGER DEFAULT 0,
    active_alert_count INTEGER DEFAULT 0,
    UNIQUE (run_id, step_index)
);

-- =========================================================
-- 6. 경로
-- =========================================================
CREATE TABLE path (
    path_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    force_mix_id BIGINT REFERENCES force_mix_candidate(force_mix_id) ON DELETE SET NULL,
    ugv_id INTEGER REFERENCES ugv(ugv_id) ON DELETE CASCADE,

    route_kind VARCHAR(20) NOT NULL CHECK (route_kind IN ('initial', 'updated', 'alternative')),
    route_rank INTEGER DEFAULT 1,
    is_selected BOOLEAN DEFAULT FALSE,

    start_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,
    goal_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,

    parent_path_id BIGINT REFERENCES path(path_id) ON DELETE SET NULL,
    trigger_event_id BIGINT,
    trigger_reason VARCHAR(100),
    reason_summary TEXT,

    physical_cost DOUBLE PRECISION,
    risk_cost DOUBLE PRECISION,
    total_cost DOUBLE PRECISION,
    eta_minutes DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE path_node (
    node_id BIGSERIAL PRIMARY KEY,
    path_id BIGINT NOT NULL REFERENCES path(path_id) ON DELETE CASCADE,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE RESTRICT,
    order_index INTEGER NOT NULL,
    sim_time_index INTEGER,
    arrival_eta_min DOUBLE PRECISION,
    UNIQUE (path_id, order_index)
);

CREATE TABLE route_cell_reservation (
    reservation_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    path_id BIGINT NOT NULL REFERENCES path(path_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    ugv_id INTEGER REFERENCES ugv(ugv_id) ON DELETE SET NULL,
    sim_time_index INTEGER NOT NULL,
    cell_id BIGINT NOT NULL REFERENCES grid_cell(cell_id) ON DELETE CASCADE,
    UNIQUE (run_id, sim_time_index, cell_id)
);

-- =========================================================
-- 7. 상태 / 로그 / KPI / 알림
-- =========================================================
CREATE TABLE mission_kpi (
    kpi_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    force_mix_id BIGINT REFERENCES force_mix_candidate(force_mix_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE SET NULL,

    mission_completion_rate DOUBLE PRECISION,
    survival_rate DOUBLE PRECISION,
    estimated_loss_rate DOUBLE PRECISION,
    avg_wait_time DOUBLE PRECISION,
    operator_utilization DOUBLE PRECISION,
    bottleneck_index DOUBLE PRECISION,
    tail_risk DOUBLE PRECISION,
    safety_margin DOUBLE PRECISION
);

CREATE TABLE run_summary (
    summary_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL UNIQUE REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    overall_success_prob DOUBLE PRECISION,
    estimated_loss_rate DOUBLE PRECISION,
    manpower_saved INTEGER,
    remaining_time_min DOUBLE PRECISION,
    current_phase VARCHAR(30),
    recommended_force_mix VARCHAR(50),
    reroute_recommended BOOLEAN DEFAULT FALSE,
    latest_reason_summary TEXT
);

CREATE TABLE unit_status_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE CASCADE,
    unit_id INTEGER NOT NULL REFERENCES mission_unit(unit_id) ON DELETE CASCADE,

    current_path_id BIGINT REFERENCES path(path_id) ON DELETE SET NULL,
    updated_path_id BIGINT REFERENCES path(path_id) ON DELETE SET NULL,

    assigned_ugv_count INTEGER,
    sos_count INTEGER DEFAULT 0,
    queue_length INTEGER DEFAULT 0,
    eta_minutes DOUBLE PRECISION,
    mission_success_prob DOUBLE PRECISION,
    estimated_loss_rate DOUBLE PRECISION,
    ltwr_grade VARCHAR(10),

    current_status VARCHAR(30),
    card_reason_summary TEXT
);

CREATE TABLE ugv_state_log (
    log_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    ugv_id INTEGER NOT NULL REFERENCES ugv(ugv_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE SET NULL,

    current_cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,
    is_sos BOOLEAN DEFAULT FALSE,
    status VARCHAR(30),
    applied_speed_kmph DOUBLE PRECISION,
    remaining_time_min DOUBLE PRECISION,
    wait_time_min DOUBLE PRECISION,
    neglect_time_min DOUBLE PRECISION,
    mode VARCHAR(30),
    forecast_offset_hr INTEGER CHECK (forecast_offset_hr BETWEEN 0 AND 3)
);

CREATE TABLE event_log (
    event_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    ugv_id INTEGER REFERENCES ugv(ugv_id) ON DELETE SET NULL,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE SET NULL,

    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    event_time TIMESTAMP NOT NULL,
    resolved_time TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    message TEXT
);

CREATE TABLE operator_assignment_log (
    assignment_id BIGSERIAL PRIMARY KEY,
    operator_id INTEGER NOT NULL REFERENCES operator(operator_id) ON DELETE CASCADE,
    ugv_id INTEGER NOT NULL REFERENCES ugv(ugv_id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES event_log(event_id) ON DELETE SET NULL,
    assigned_time TIMESTAMP,
    released_time TIMESTAMP,
    assign_status VARCHAR(30)
);

CREATE TABLE alert_log (
    alert_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE SET NULL,
    cell_id BIGINT REFERENCES grid_cell(cell_id) ON DELETE SET NULL,

    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    title VARCHAR(120),
    message TEXT,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recommendation_log (
    recommendation_id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    unit_id INTEGER REFERENCES mission_unit(unit_id) ON DELETE SET NULL,
    step_id BIGINT REFERENCES simulation_step(step_id) ON DELETE SET NULL,

    recommendation_type VARCHAR(50) NOT NULL,
    title VARCHAR(120),
    reason_summary TEXT,
    old_path_id BIGINT REFERENCES path(path_id) ON DELETE SET NULL,
    new_path_id BIGINT REFERENCES path(path_id) ON DELETE SET NULL,
    recommended_force_mix_id BIGINT REFERENCES force_mix_candidate(force_mix_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 8. 인덱스
-- =========================================================
CREATE INDEX idx_grid_cell_xy ON grid_cell(grid_x, grid_y);
CREATE INDEX idx_grid_cell_lonlat ON grid_cell(lon, lat);

CREATE INDEX idx_run_scenario ON simulation_run(scenario_id);
CREATE INDEX idx_target_run ON mission_target(run_id);
CREATE INDEX idx_unit_run ON mission_unit(run_id);
CREATE INDEX idx_assignment_unit ON unit_assignment(unit_id);

CREATE INDEX idx_weather_obs_run_cell_time
ON weather_observed(run_id, cell_id, observed_time);

CREATE INDEX idx_weather_fcst_run_cell_time
ON weather_forecast(run_id, cell_id, forecast_time, forecast_offset_hr);

CREATE INDEX idx_ltwr_run_cell_time
ON ltwr_assessment(run_id, cell_id, forecast_time, forecast_offset_hr);

CREATE INDEX idx_tactical_run_cell_time
ON tactical_impact(run_id, cell_id, forecast_time, forecast_offset_hr);

CREATE INDEX idx_risk_run_unit_time
ON mission_risk_layer(run_id, unit_id, forecast_time, forecast_offset_hr);

CREATE INDEX idx_force_mix_run_unit
ON force_mix_candidate(run_id, unit_id);

CREATE INDEX idx_ugv_run_unit
ON ugv(run_id, unit_id);

CREATE INDEX idx_operator_run_unit
ON operator(run_id, unit_id);

CREATE INDEX idx_step_run_idx
ON simulation_step(run_id, step_index);

CREATE INDEX idx_path_run_unit_kind
ON path(run_id, unit_id, route_kind);

CREATE INDEX idx_path_node_path_order
ON path_node(path_id, order_index);

CREATE INDEX idx_reservation_run_time_cell
ON route_cell_reservation(run_id, sim_time_index, cell_id);

CREATE INDEX idx_kpi_run_unit
ON mission_kpi(run_id, unit_id);

CREATE INDEX idx_snapshot_run_step_unit
ON unit_status_snapshot(run_id, step_id, unit_id);

CREATE INDEX idx_ugv_log_run_ugv_step
ON ugv_state_log(run_id, ugv_id, step_id);

CREATE INDEX idx_event_run_time
ON event_log(run_id, event_time);

CREATE INDEX idx_alert_run_step
ON alert_log(run_id, step_id);

CREATE INDEX idx_reco_run_step
ON recommendation_log(run_id, step_id);