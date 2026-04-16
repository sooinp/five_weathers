"""
backend/app/db/schemas/dashboard.py

대시보드 조회 API용 Pydantic 응답 스키마.

[용어 정의]
  진행상황    : CREATED="진행 전" / RUNNING="진행중" / COMPLETED="진행 완료"
  임무성공률  : 0 ~ 100 (%)
  대기열발생시간(구 자산피해율): -100 ~ 100 (%)  ← DB 컬럼명은 asset_damage_rate 유지
"""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional

# ── 진행상황 한국어 매핑 ─────────────────────────────────
STATUS_LABEL: dict[str, str] = {
    "CREATED":   "진행 전",    # ← 변경: 대기중 → 진행 전
    "RUNNING":   "진행중",
    "COMPLETED": "진행 완료",  # ← 변경: 완료 → 진행 완료
    "FAILED":    "실패",
    "CANCELLED": "취소",
}


def _sec_to_hms(sec: int | None) -> str | None:
    if sec is None:
        return None
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── 스냅샷 (raw ORM 응답) ────────────────────────────────
class SnapshotOut(BaseModel):
    id: int
    run_id: int
    status: str
    phase: str | None
    progress_pct: int

    # 임무성공률: 0 ~ 100 (%)
    mission_success_rate: float | None = Field(None, ge=0.0, le=100.0)

    # 대기열 발생시간 (구 자산피해율): -100 ~ 100 (%)
    # DB 컬럼명(asset_damage_rate) → validation_alias로 ORM 매핑 유지
    queue_occurrence_rate: float | None = Field(
        None,
        ge=-100.0,
        le=100.0,
        validation_alias="asset_damage_rate",
        description="대기열 발생시간 (-100 ~ 100 %)",
    )

    remaining_time_sec: int | None
    aoi_remaining_sec: int | None
    queue_length: int
    timestamp: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,  # alias 외 필드명으로도 접근 허용
    }


# ── 진행상황 상단 KPI 바 ─────────────────────────────────
class RunStatusOut(BaseModel):
    """GET /api/runs/{run_id}/status 전용 응답."""
    run_id: int
    status: str                  # RUNNING | COMPLETED | …
    status_label: str            # 진행 전 | 진행중 | 진행 완료 | 실패 | 취소

    # 임무성공률: 0 ~ 100 (%)
    mission_success_rate: float | None = Field(None, ge=0.0, le=100.0)

    # 대기열 발생시간 (구 자산피해율): -100 ~ 100 (%)
    queue_occurrence_rate: float | None = Field(
        None, ge=-100.0, le=100.0,
        description="대기열 발생시간 (-100 ~ 100 %)",
    )

    remaining_time_sec: int | None
    remaining_time_hms: str | None
    aoi_remaining_sec: int | None
    aoi_remaining_hms: str | None
    aoi_total_sec: int | None
    aoi_total_hms: str | None
    timestamp: datetime | None

    @classmethod
    def from_snapshot_and_mission(
        cls,
        run_id: int,
        status: str,
        snapshot: "SnapshotOut | None",
        mission_duration_min: int | None,
    ) -> "RunStatusOut":
        aoi_total_sec = mission_duration_min * 60 if mission_duration_min else None
        aoi_rem = snapshot.aoi_remaining_sec if snapshot else None
        return cls(
            run_id=run_id,
            status=status,
            status_label=STATUS_LABEL.get(status, status),
            mission_success_rate=snapshot.mission_success_rate if snapshot else None,
            queue_occurrence_rate=snapshot.queue_occurrence_rate if snapshot else None,
            remaining_time_sec=snapshot.remaining_time_sec if snapshot else None,
            remaining_time_hms=_sec_to_hms(snapshot.remaining_time_sec if snapshot else None),
            aoi_remaining_sec=aoi_rem,
            aoi_remaining_hms=_sec_to_hms(aoi_rem),
            aoi_total_sec=aoi_total_sec,
            aoi_total_hms=_sec_to_hms(aoi_total_sec),
            timestamp=snapshot.timestamp if snapshot else None,
        )
    

# ── 상단 헤더 ─────────────────────────────────────────────
class HomeAssetModeItem(BaseModel):
    key: str
    label: str
    count: int


class HomeSummaryOut(BaseModel):
    role: str
    role_label: str
    current_time: str
    remaining_time: str
    mission_notice: Optional[str] = None
    unit_label: Optional[str] = None
    asset_status_label: str = "자산현황"
    asset_modes: list[HomeAssetModeItem]
    selected_mode: str
    latest_run_id: int | None = None
    latest_mission_id: int | None = None
    has_pending_briefing: bool = False
    assigned_echelon_no: int | None = None

# ── 남은 시간 ─────────────────────────────────────────────
class RemainingTimeOut(BaseModel):
    """
    GET /api/runs/{run_id}/remaining-time 전용 응답.

    매 호출 시 started_at 기준으로 서버에서 직접 계산.
    snapshot 의존 없이 항상 정확한 값 반환.

    카운트다운 공식:
        total_sec     = mission_duration_min × 60
        elapsed_sec   = now − started_at  (RUNNING 상태일 때)
        remaining_sec = max(0, total_sec − elapsed_sec)
    """
    run_id: int
    status: str
    status_label: str            # 진행 전 | 진행중 | 진행 완료

    total_sec: int
    total_hms: str               # "00:30:00"
    elapsed_sec: int
    elapsed_hms: str             # "00:17:26"
    remaining_sec: int
    remaining_hms: str           # "00:12:34"

    progress_pct: float          # elapsed / total × 100  (0~100)
    is_expired: bool
    started_at: datetime | None
    calculated_at: datetime


# ── 지휘관/통제관 공통 스키마 ────────────────────────────────

class CommanderModeItem(BaseModel):
    key: str          # balanced | recon | rapid
    label: str        # 균형 | 정찰 | 신속
    selected: bool = False


class CommanderMetricOut(BaseModel):
    success_rate: float | None = None   # 임무 성공률 (%)
    risk_rate: float | None = None      # 임무 위험률 (%)


class CommanderActionState(BaseModel):
    execute_enabled: bool = True
    terminate_enabled: bool = False
    dispatch_enabled: bool = True
    replan_enabled: bool = False


class CommanderHomeOut(BaseModel):
    run_id: int
    role_label: str = "지휘관"
    tabs: list[str] = ["지휘관", "자산 현황"]
    selected_tab: str = "지휘관"
    modes: list[CommanderModeItem] = []
    selected_mode: str = "balanced"
    metrics: CommanderMetricOut = CommanderMetricOut()
    actions: CommanderActionState = CommanderActionState()


class EchelonRowOut(BaseModel):
    echelon_id: int
    echelon_label: str        # "1제대"
    ugv_count: int
    departure_eta: str        # "02:20:00"
    arrival_eta: str          # "07:30:00"
    recon_duration: str       # "00:30:00"


class CommanderEchelonsOut(BaseModel):
    run_id: int
    rows: list[EchelonRowOut]


class CommanderMapHeaderOut(BaseModel):
    current_time_label: str
    remaining_time_label: str
    selected_layer: str = "risk"
    layer_tabs: list[str] = ["risk", "mobility", "sensor"]


class CommanderMapMarkerOut(BaseModel):
    marker_type: str          # start | target | ugv
    label: str
    lat: float
    lon: float
    echelon_id: int | None = None


class CommanderRouteLineOut(BaseModel):
    route_id: int
    echelon_id: int
    label: str
    points: list[list[float]]   # [[lat, lon], ...]
    is_primary: bool = True


class CommanderMapOut(BaseModel):
    run_id: int
    header: CommanderMapHeaderOut
    markers: list[CommanderMapMarkerOut]
    routes: list[CommanderRouteLineOut]
    legend: list[str]
    overlay_url: str | None = None


class CommanderPanelsOut(BaseModel):
    run_id: int
    mission_success_rate: float | None = None
    mission_risk_rate: float | None = None
    queue_count: int = 0
    active_alerts: list[str] = []


class CommanderActionResultOut(BaseModel):
    ok: bool
    action: str
    run_id: int
    message: str
    issued_at: datetime


# ── 지휘관 대시보드 통합 API ──────────────────────────────────

class CommanderDashboardOut(BaseModel):
    """GET /api/runs/{run_id}/commander/dashboard 통합 응답."""
    run_id: int
    role_label: str = "지휘관"
    current_time: str
    remaining_time: str
    selected_mode: str = "balanced"
    mode_buttons: list[CommanderModeItem] = []
    metrics: CommanderMetricOut = CommanderMetricOut()
    echelons: list[EchelonRowOut] = []
    map: dict = {}
    actions: CommanderActionState = CommanderActionState()


# ── 자산 현황 ────────────────────────────────────────────────

class AssetStatusItemOut(BaseModel):
    """제대별 자산 현황 항목 1개."""
    unit_scope: int
    unit_label: str           # "1제대"
    troop_count: int | None = None
    operator_count: int | None = None
    sensor_count: int | None = None
    available_ugv_count: int | None = None
    target_count: int | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None


class AssetStatusSummaryOut(BaseModel):
    """자산 현황 요약 (부대 기본자산 패널 상단 표시용)."""
    total_units: int        # 총 제대 수
    total_controllers: int  # 총 통제관 수
    total_ugv: int          # 총 정찰 UGV 수 (sensor_count 합산)
    lost_ugv: int           # 총 손실 UGV 수 (sensor_count - available_ugv_count 합산)


class AssetStatusListOut(BaseModel):
    """GET /api/runs/{run_id}/asset-status 응답."""
    run_id: int
    role: str
    summary: AssetStatusSummaryOut | None = None
    items: list[AssetStatusItemOut]


class AssetStatusPatchItem(BaseModel):
    unit_scope: int
    troop_count: int | None = None
    operator_count: int | None = None
    sensor_count: int | None = None
    available_ugv_count: int | None = None
    target_count: int | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None


class AssetStatusPatchIn(BaseModel):
    """PATCH /api/runs/{run_id}/asset-status 요청 바디."""
    items: list[AssetStatusPatchItem]


# ── 임무 하달 / 통제관 브리핑 ────────────────────────────────

class DispatchResultOut(BaseModel):
    """POST /api/runs/{run_id}/dispatch 응답."""
    ok: bool
    run_id: int
    message: str
    issued_at: datetime


class OperatorBriefingOut(BaseModel):
    """GET /api/runs/{run_id}/operator/briefing 응답."""
    run_id: int
    unit_label: str
    notice: str
    asset_status: AssetStatusItemOut | None = None
    mission_info: dict | None = None
    map: dict | None = None


class AcknowledgeResultOut(BaseModel):
    """POST /api/runs/{run_id}/operator/acknowledge 응답."""
    ok: bool
    run_id: int
    message: str
    acknowledged_at: datetime


class OperatorAssetPanelOut(BaseModel):
    """통제관 자산 패널 메타 (우측 토글 UI용)."""
    title: str = "기본자산"
    tabs: list[str]          # ["부대", "2제대"]
    default_open: bool = False


class OperatorDashboardOut(BaseModel):
    """GET /api/runs/{run_id}/operator/dashboard 응답."""
    run_id: int
    role_label: str = "통제관"
    # ── 상단 탭 ─────────────────────────────────────────────
    tabs: list[str] = ["통제관", "자산 현황"]
    selected_tab: str = "통제관"
    # ── 기본 정보 ────────────────────────────────────────────
    unit_label: str
    current_time: str
    remaining_time: str
    selected_mode: dict | None = None   # {"key": "balanced", "label": "균형"}
    # ── KPI 지표 ─────────────────────────────────────────────
    metrics: CommanderMetricOut = CommanderMetricOut()
    # ── 제대 요약 표 (자기 제대 1행만) ─────────────────────────
    echelons: list[EchelonRowOut] = []
    # ── 액션 버튼 상태 ───────────────────────────────────────
    actions: CommanderActionState = CommanderActionState()
    # ── 맵 레이어 ────────────────────────────────────────────
    map: dict | None = None
    # ── 자산 패널 메타 ───────────────────────────────────────
    asset_panel: OperatorAssetPanelOut | None = None
    # ── 하위 호환 (기존 asset_status 필드 유지) ──────────────
    asset_status: AssetStatusItemOut | None = None


# ── 지휘관 설정 (missions/{id}/commander-setup) ──────────────

class CommanderSetupTargetItem(BaseModel):
    seq: int
    label: str
    lat: float
    lon: float


class CommanderSetupMapOut(BaseModel):
    center_lat: float
    center_lon: float
    zoom: int = 8
    targets: list[CommanderSetupTargetItem]


class CommanderSetupRowOut(BaseModel):
    echelon_id: int
    recon_target: int | None
    recon_time_sec: int


class CommanderSetupOut(BaseModel):
    """GET /api/missions/{mission_id}/commander-setup 응답."""
    mission_id: int
    map: CommanderSetupMapOut
    rows: list[CommanderSetupRowOut]
    

# ── 대기열 (SOS 기반 FIFO 카운트업) ─────────────────────

class SosQueueItem(BaseModel):
    """대기열에서 SOS 처리를 기다리는 UGV 1개 항목."""
    sos_event_id: int
    unit_no: int
    asset_code: str               # 화면: "UGV-2", "UGV-1"

    sos_at: datetime              # SOS 발생 시각 = 카운트업 시작점
    elapsed_sec: int              # 누적 대기시간 (초) — 카운트업
    elapsed_min: int              # 화면 표시용 (12m, 7m)
    elapsed_hms: str              # HH:MM:SS

    fifo_position: int            # FIFO 순서 (1 = 가장 먼저 SOS 발생)
    # 1번이 가장 먼저 처리 대상 (일대일 대응)

    is_resolved: bool             # True = 처리 완료 (resolved_at 있음)
    resolved_at: datetime | None

    lat: float | None
    lon: float | None
    calculated_at: datetime


class SosQueueOut(BaseModel):
    """GET /api/runs/{run_id}/queue/danger 전용 응답."""
    run_id: int
    danger_count: int             # 현재 SOS 대기 중인 UGV 수 (미처리)
    items: list[SosQueueItem]     # fifo_position 오름차순 (먼저 SOS 발생 순)


# ── 대기열 발생시간 (현재 대기 중인 UGV) ─────────────────
class QueueActiveItem(BaseModel):
    """현재 대기열에 있는 UGV 1개 항목."""
    asset_code: str
    unit_no: int
    entered_at: datetime         # 대기열 진입 시각 (발생시간)
    elapsed_sec: int
    elapsed_min: int             # 화면 표시용 (12m, 7m)
    wait_time_sec: int | None
    wait_time_min: int | None
    priority_score: float | None
    lat: float | None
    lon: float | None


class QueueActiveOut(BaseModel):
    """GET /api/runs/{run_id}/queue/active 전용 응답."""
    run_id: int
    active_count: int
    items: list[QueueActiveItem]


# ── 임무성공률 시계열 ─────────────────────────────────────
class SuccessRatePoint(BaseModel):
    """시계열 그래프 한 점."""
    timestamp: datetime
    value: float = Field(..., ge=0.0, le=100.0)  # 임무성공률: 0~100 (%)


class MissionSuccessRateOut(BaseModel):
    """GET /api/runs/{run_id}/success-rate 전용 응답."""
    run_id: int
    current: float | None = Field(None, ge=0.0, le=100.0)  # 임무성공률: 0~100 (%)
    history: list[SuccessRatePoint]
    projected: dict[str, float | None]   # {"T1": 82.5, "T2": 85.0, "T3": 87.3}


# ── 나머지 공통 응답 스키마 ───────────────────────────────

class PanelOut(BaseModel):
    id: int
    run_id: int
    panel_type: str
    data: dict | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class UnitOut(BaseModel):
    id: int
    run_id: int
    unit_no: int
    asset_code: str
    status: str
    lat: float | None
    lon: float | None
    message: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueueEventOut(BaseModel):
    id: int
    run_id: int
    asset_code: str
    wait_time_sec: int | None
    priority_score: float | None
    event_type: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    run_id: int
    severity: str
    alert_type: str
    message: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class RouteOut(BaseModel):
    id: int
    run_id: int
    unit_no: int
    route_type: str
    reason: str | None
    geojson: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MapLayerOut(BaseModel):
    id: int
    run_id: int
    layer_type: str
    time_slot: str | None
    file_path: str | None
    meta: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class KpiOut(BaseModel):
    id: int
    run_id: int
    success_rate: float | None
    damage_rate: float | None
    makespan_sec: int | None
    queue_kpi: dict | None
    bottleneck_index: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationOut(BaseModel):
    id: int
    run_id: int
    candidate_id: int | None
    score: float | None
    is_selected: bool
    rationale: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 정찰구역 ──────────────────────────────────────────────

class PatrolAreaItem(BaseModel):
    """현재 정찰 중이거나 완료된 UGV 1개 항목."""
    event_id: int
    run_id: int
    unit_no: int
    asset_code: str
    target_seq: int               # 목적지 순번 (1, 2, 3)
    target_lat: float
    target_lon: float

    patrol_duration_sec: int      # 총 정찰 시간 (초)
    patrol_duration_hms: str      # "00:30:00"

    arrived_at: datetime          # 도착 시각 = 카운트다운 시작
    is_completed: bool            # completed_at 값 유무

    # 카운트다운 실시간 값 (is_completed=True이면 모두 0)
    elapsed_sec: int
    elapsed_hms: str              # "00:17:26"
    remaining_sec: int
    remaining_hms: str            # "00:12:34"
    progress_pct: float           # elapsed / total × 100

    is_expired: bool              # remaining=0 이면서 아직 RUNNING
    calculated_at: datetime


class PatrolAreaOut(BaseModel):
    """GET /api/runs/{run_id}/patrol-area 전용 응답."""
    run_id: int
    active_count: int             # 현재 정찰 중인 UGV 수
    total_count: int              # 전체 patrol 이벤트 수 (완료 포함)
    items: list[PatrolAreaItem]


# ── 부대 정보 ──────────────────────────────────────────────

class UnitInfoOut(BaseModel):
    """GET /api/runs/{run_id}/unit-info 전용 응답."""
    run_id: int
    mission_id: int

    echelon_no: int               # 몇 제대 (1, 2, 3 …)
    echelon_label: str            # 화면 표시용: "1제대", "2제대" …

    total_ugv: int                # 운용 UGV 수 (mission.total_ugv)
    max_ugv_count: int            # 편성 최대 UGV 수 (mission.max_ugv_count)


# ── 운용 UGV 수 ───────────────────────────────────────────

# ── 현재경로 효과 ──────────────────────────────────────────

class RouteEffectOut(BaseModel):
    """
    GET /api/runs/{run_id}/route-effect 전용 응답.

    최적경로(현재 선택) vs 차선책(두 번째 최적경로) KPI 비교 delta.
    화면 표시:
      임무성공률  +12%  ← success_rate_delta
      자산피해율  -7%   ← damage_rate_delta
    """
    run_id: int

    # ── 최적경로 KPI ──────────────────────────────────────
    optimal_success_rate: float | None = Field(None, ge=0.0, le=100.0)
    optimal_damage_rate: float | None = Field(None, ge=-100.0, le=100.0)

    # ── 차선책 KPI ────────────────────────────────────────
    alt_success_rate: float | None = Field(None, ge=0.0, le=100.0)
    alt_damage_rate: float | None = Field(None, ge=-100.0, le=100.0)

    # ── Delta (최적 − 차선책) ─────────────────────────────
    # 임무성공률 delta: 양수 = 최적이 더 좋음 (예: +12%)
    success_rate_delta: float | None = Field(
        None, description="임무성공률 delta (최적 − 차선책), %p 단위"
    )
    success_rate_delta_label: str | None = None   # "+12%" / "-3%"

    # 대기열 발생시간 delta: 음수 = 최적이 더 좋음 (예: -7%)
    damage_rate_delta: float | None = Field(
        None, description="대기열 발생시간 delta (최적 − 차선책), %p 단위"
    )
    damage_rate_delta_label: str | None = None    # "-7%" / "+2%"

    created_at: datetime | None = None


# ── 운용 UGV 수 ───────────────────────────────────────────

class UgvCountOut(BaseModel):
    """GET /api/runs/{run_id}/ugv-count 전용 응답."""
    run_id: int
    mission_id: int

    total_ugv: int = Field(..., ge=0, le=4, description="운용 UGV 수 (0 ~ 4대)")
    # 미션 생성 시 사용자가 입력한 운용 UGV 대 수.
    max_ugv_count: int            # 편성 가능 최대 UGV 수 (상한 기준값)

    # 실시간 상태별 분류 (run_units 기준)
    active_count: int             # MOVING + STANDBY 상태 UGV 수
    queued_count: int             # QUEUED 상태 UGV 수
    done_count: int               # DONE 상태 UGV 수
    sos_count: int                # SOS 상태 UGV 수


# ── 중앙 그리드 맵 ────────────────────────────────────────

LAYER_LABEL: dict[str, str] = {
    "RISK":     "위험도",
    "MOBILITY": "기동성(토양수분)",
    "SENSOR":   "센서(가시성)",
}


class MapLayerInfo(BaseModel):
    """레이어 탭 1개의 정보."""
    layer_type: str               # RISK | MOBILITY | SENSOR
    layer_label: str              # 위험도 | 기동성(토양수분) | 센서(가시성)
    file_path: str | None         # 서버 내 파일 경로 (없으면 수신 대기 중)
    meta: dict | None = None
    is_ready: bool                # 파일 경로가 존재하면 True


class MapMarker(BaseModel):
    """맵 위에 표시되는 마커 1개."""
    marker_type: str
    # UGV | DEPARTURE | TARGET | FRIENDLY
    label: str                    # "UGV-1", "출발지", "도착지", "유인기"
    unit_no: int | None = None    # UGV만 해당
    lat: float
    lon: float
    status: str | None = None     # UGV 상태 (MOVING / QUEUED / SOS / DONE)
    seq: int | None = None        # TARGET의 목적지 순번 (1, 2, 3)


class MapViewOut(BaseModel):
    """
    GET /api/runs/{run_id}/map-view 전용 응답.

    중앙 그리드 맵 렌더링에 필요한 모든 데이터를 단일 응답으로 반환.
    - layers  : 위험도 / 기동성(토양수분) / 센서(가시성) 레이어 정보
    - markers : UGV 현재 위치 + 출발지 + 도착지
    - center  : 지도 초기 중심점 (출발지 기준)
    """
    run_id: int
    mission_id: int

    # 탭 레이어 3종 순서 고정: RISK → MOBILITY → SENSOR
    layers: list[MapLayerInfo]

    # 지도 마커 목록
    markers: list[MapMarker]

    # 지도 초기 중심점 (출발지 기준)
    center_lat: float
    center_lon: float


# ── LTWR 현황 ─────────────────────────────────────────────

LTWR_SLOT_LABEL: dict[str, str] = {
    "T0": "T+0: Present Status",
    "T1": "T+1: Prediction",
    "T2": "T+2: Prediction",
    "T3": "T+3: Prediction",
}


class LtwrSlotOut(BaseModel):
    """LTWR 시간대 슬롯 1개 (T+0 / T+1 / T+2 / T+3)."""
    time_slot: str                # T0 | T1 | T2 | T3
    slot_label: str               # "T+0: Present Status" | "T+1: Prediction" …
    file_path: str | None         # 기상 예측 지도 파일 경로 (없으면 수신 대기)
    meta: dict | None = None      # 추가 메타정보 (해상도, 생성 시각 등)
    is_ready: bool                # file_path가 있으면 True
    created_at: datetime | None = None


class LtwrViewOut(BaseModel):
    """
    GET /api/runs/{run_id}/ltwr-view 전용 응답.

    우측 스크롤 박스에 표시할 T+0 ~ T+3 기상 예측 지도 슬롯 목록.
    slots 는 T0 → T1 → T2 → T3 순서로 고정 반환.
    """
    run_id: int
    slots: list[LtwrSlotOut]      # 항상 4개 (T0~T3), is_ready=False면 수신 대기
    ready_count: int              # 수신 완료된 슬롯 수 (0~4)
