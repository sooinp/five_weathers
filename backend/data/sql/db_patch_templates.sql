-- DB patch templates for fiveweathersDB
-- Generated to match the current project schema and login flow.
-- Safe to review and run selectively in pgAdmin4.

BEGIN;

-- ============================================================
-- 1) Users: commander / operator accounts
-- ============================================================
-- user1 / user2 / user3 must be operator accounts.
-- Password hashes below were generated with the same bcrypt settings used by the project.
-- admin 계정은 이미 별도로 존재한다고 보고 여기서는 건드리지 않습니다.

INSERT INTO users (username, password_hash, role)
VALUES
  ('user1', '$2b$12$692jNYTpsXfWrQhHRsO1yeqPD1c7xJCMLoTUtpoiuCj/gUUwFTzhq', 'operator'),
  ('user2', '$2b$12$f3VtcfLVRf/bYObNGFmYIusn2qLGWgzsxwENmsBtBvxL/lXarrNg2', 'operator'),
  ('user3', '$2b$12$AstGeLV5rQ1cEBNStdAew.QRBfmIhiDMXTFVrpRTRpyZngA/Cbf/.', 'operator')
ON CONFLICT (username)
DO UPDATE SET
  password_hash = EXCLUDED.password_hash,
  role = EXCLUDED.role;

-- ============================================================
-- 2) Mission force mix candidates
-- ============================================================
-- Used by recommendation / candidate linkage.
-- Replace mission_id and config JSON as needed.

INSERT INTO mission_force_mix_candidates (mission_id, candidate_name, ugv_count, config)
VALUES
  (14, 'balanced-default', 2, '{"mode":"balanced","unit":"1제대"}'::jsonb),
  (14, 'recon-default', 3, '{"mode":"recon","unit":"1제대"}'::jsonb),
  (14, 'rapid-default', 4, '{"mode":"rapid","unit":"1제대"}'::jsonb);

-- ============================================================
-- 3) Asset status per run / unit
-- ============================================================
-- Used by commander/operator asset status panels.
-- user_id should usually be:
--   admin -> commander edits
--   user1/user2/user3 -> operator edits

INSERT INTO run_asset_statuses (
  run_id,
  user_id,
  unit_scope,
  troop_count,
  operator_count,
  sensor_count,
  available_ugv_count,
  target_count,
  departure_time,
  arrival_time
)
VALUES
  (14, 2, 1, 1, 1, 2, 2, 1, '2026-04-22 03:00:00+09', '2026-04-22 04:50:00+09'),
  (14, 2, 2, 1, 1, 4, 4, 1, '2026-04-22 03:00:00+09', '2026-04-22 05:30:00+09'),
  (14, 2, 3, 1, 1, 3, 3, 1, '2026-04-22 03:00:00+09', '2026-04-22 06:10:00+09');

-- ============================================================
-- 4) Map layers
-- ============================================================
-- Used by LTWR / risk / mobility / sensor map APIs.
-- file_path can point to HTML, PNG, TIF, etc. depending on your renderer.

INSERT INTO run_map_layers (run_id, layer_type, time_slot, file_path, meta)
VALUES
  (14, 'RISK',     NULL, '/sim-maps/current.html', '{"source":"html-sim-map"}'::jsonb),
  (14, 'MOBILITY', NULL, '/sim-maps/current.html', '{"source":"html-sim-map"}'::jsonb),
  (14, 'SENSOR',   NULL, '/sim-maps/current.html', '{"source":"html-sim-map"}'::jsonb),
  (14, 'LTWR',     'T0', '/api/ltwr/maps/T0?kind=total', '{"slot":"h+0"}'::jsonb),
  (14, 'LTWR',     'T1', '/api/ltwr/maps/T1?kind=total', '{"slot":"h+1"}'::jsonb),
  (14, 'LTWR',     'T2', '/api/ltwr/maps/T2?kind=total', '{"slot":"h+2"}'::jsonb),
  (14, 'LTWR',     'T3', '/api/ltwr/maps/T3?kind=total', '{"slot":"h+3"}'::jsonb);

-- ============================================================
-- 5) Alerts
-- ============================================================
-- Used by commander/operator alert panels and websocket notification history.

INSERT INTO run_alerts (run_id, severity, alert_type, message, timestamp)
VALUES
  (14, 'INFO',  'DISPATCH',      '임무가 하달되었습니다.', now()),
  (14, 'WARN',  'QUEUE_OVERFLOW','UGV-2 대기 시간이 증가하고 있습니다.', now()),
  (14, 'ERROR', 'SOS',           '제3제대 UGV-1 SOS 발생', now());

-- ============================================================
-- 6) Queue events
-- ============================================================
-- Used by /queue/active.

INSERT INTO run_queue_events (run_id, asset_code, wait_time_sec, priority_score, event_type, timestamp)
VALUES
  (14, 'UGV-2', 720, 0.91, 'ENTER', now() - interval '12 minute'),
  (14, 'UGV-1', 420, 0.73, 'ENTER', now() - interval '7 minute');

-- ============================================================
-- 7) SOS events
-- ============================================================
-- Used by /queue/danger.

INSERT INTO run_sos_events (run_id, unit_no, asset_code, event_type, sos_at, resolved_at, lat, lon)
VALUES
  (14, 3, 'UGV-1', 'SOS', now() - interval '15 minute', NULL, 54.4900, 18.3200),
  (14, 2, 'UGV-2', 'SOS_RESOLVED', now() - interval '25 minute', now() - interval '5 minute', 54.4930, 18.3120);

-- ============================================================
-- 8) Patrol events
-- ============================================================
-- Used by patrol-area countdown.

INSERT INTO run_patrol_events (
  run_id,
  unit_no,
  asset_code,
  target_seq,
  target_lat,
  target_lon,
  patrol_duration_sec,
  arrived_at,
  completed_at
)
VALUES
  (14, 1, 'UGV-1', 1, 54.493171, 18.312422, 1800, now() - interval '10 minute', NULL),
  (14, 2, 'UGV-2', 2, 54.490627, 18.320923, 3600, now() - interval '20 minute', NULL),
  (14, 3, 'UGV-3', 3, 54.489800, 18.327500, 1800, now() - interval '40 minute', now() - interval '10 minute');

-- ============================================================
-- 9) Data assets / mission assets / run input assets
-- ============================================================
-- Used when you want DB-tracked file references.

INSERT INTO data_assets (asset_type, file_path, meta)
VALUES
  ('STATIC_GRID', 'data/map/static/Test_sim_input_200m_bbox_2km.parquet', '{"label":"입력 지도 parquet"}'::jsonb),
  ('RISK_MAP',    'data/static/animated_gar_overlay_with_paths_persistent_alerts_balance_11.html', '{"label":"시뮬레이션 맵 html"}'::jsonb),
  ('LTWR_MAP',    '/api/ltwr/maps/T1?kind=total', '{"label":"LTWR h+1"}'::jsonb);

-- Link the newest assets to a mission and run.
INSERT INTO mission_assets (mission_id, asset_id)
SELECT 14, id
FROM data_assets
WHERE asset_type IN ('STATIC_GRID', 'RISK_MAP');

INSERT INTO run_input_assets (run_id, asset_id, role)
SELECT 14, id,
  CASE asset_type
    WHEN 'STATIC_GRID' THEN 'STATIC_GRID'
    WHEN 'RISK_MAP' THEN 'RISK_T0'
    WHEN 'LTWR_MAP' THEN 'LTWR_T1'
    ELSE asset_type
  END
FROM data_assets
WHERE asset_type IN ('STATIC_GRID', 'RISK_MAP', 'LTWR_MAP');

COMMIT;

-- ============================================================
-- 10) Legacy scenario stack (optional)
-- ============================================================
-- These tables are not present in the current DB, but older APIs / scripts expect them.
-- Create and seed only if you intend to use scenario/grid/weather loading scripts again.

-- CREATE TABLE IF NOT EXISTS scenarios (
--   scenario_id varchar(50) PRIMARY KEY,
--   name varchar(200) NOT NULL,
--   description text,
--   created_at timestamptz NOT NULL DEFAULT now()
-- );
--
-- INSERT INTO scenarios (scenario_id, name, description)
-- VALUES
--   ('scenario_001', '기본 시나리오', '기본 운용 시나리오')
-- ON CONFLICT (scenario_id)
-- DO UPDATE SET
--   name = EXCLUDED.name,
--   description = EXCLUDED.description;
