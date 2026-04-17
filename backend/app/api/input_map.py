"""
backend/app/api/input_map.py

작전 지역 입력 맵 API — 인터랙티브 Leaflet 지도 (지휘관 입력 페이지 전용).

엔드포인트 (prefix: /api/map/input):
  GET  /html           — Leaflet HTML 서빙 (iframe src)
  GET  /terrain-image  — backend/data/map/static/*.parquet 기반 정적 지형 PNG
  GET  /markers        — 현재 마커 목록 (지도 폴링용)
  POST /markers        — 마커 업데이트 (Solara → 지도)
  POST /click          — 우클릭 지점 기록 (지도 → 백엔드)
  GET  /pending-click  — 미처리 클릭 조회 (Solara 폴링용)
"""

from __future__ import annotations

import io
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/map/input", tags=["input-map"])

_INPUT_STATIC_DIR = Path(__file__).resolve().parents[2] / "data" / "map" / "static"
_DEFAULT_RGBA = (100, 116, 139, 180)
_LC_COLORS_RGBA: dict[int, tuple[int, int, int, int]] = {
    10: (160, 210, 140, 210),   # 농지
    20: (200, 230, 170, 185),   # 초원
    30: (40, 120, 40, 220),     # 숲
    40: (150, 150, 150, 205),   # 도시
    50: (50, 130, 240, 220),    # 수역
    60: (230, 200, 90, 210),    # 도로
    80: (200, 50, 50, 230),     # 위험지형
    90: (30, 80, 200, 230),     # 하천
    100: (180, 180, 200, 185),  # 기타
}

# ── 인메모리 상태 ─────────────────────────────────────────
_marker_seq: int = 0
_last_marker_client_seq: int = 0
_markers: list = []        # [{id, unit, lat, lng, type}]

_click_seq: int = 0
_pending_clicks: list[dict] = []   # [{seq, unit, lat, lng, kind, departure}]


@lru_cache(maxsize=1)
def _get_input_parquet_path() -> Path:
    files = sorted(_INPUT_STATIC_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"입력 지도 parquet 파일 없음: {_INPUT_STATIC_DIR}")
    return files[0]


@lru_cache(maxsize=1)
def _load_input_map_df() -> pd.DataFrame:
    path = _get_input_parquet_path()
    return pd.read_parquet(path, columns=["row", "col", "lat", "lon", "lc_code"])


@lru_cache(maxsize=1)
def _get_input_map_bounds() -> dict[str, float]:
    df = _load_input_map_df()
    return {
        "min_lat": float(df["lat"].min()),
        "max_lat": float(df["lat"].max()),
        "min_lng": float(df["lon"].min()),
        "max_lng": float(df["lon"].max()),
        "center_lat": float(df["lat"].mean()),
        "center_lng": float(df["lon"].mean()),
    }


@lru_cache(maxsize=1)
def _generate_input_terrain_png_bytes() -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow 패키지가 필요합니다.") from exc

    df = _load_input_map_df()
    ny = int(df["row"].max()) + 1
    nx = int(df["col"].max()) + 1
    img_array = np.zeros((ny, nx, 4), dtype=np.uint8)

    codes = df["lc_code"].values.astype(int)
    rows = df["row"].values.astype(int)
    cols = df["col"].values.astype(int)

    color_table = np.array([
        _LC_COLORS_RGBA.get(code, _DEFAULT_RGBA) for code in codes
    ], dtype=np.uint8)
    valid = (rows >= 0) & (rows < ny) & (cols >= 0) & (cols < nx)
    img_array[rows[valid], cols[valid]] = color_table[valid]

    img = Image.fromarray(img_array, "RGBA")
    img = img.resize((nx * 16, ny * 16), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _build_input_map_html(backend_url: str | None = None) -> str:
    bounds = _get_input_map_bounds()
    min_lat = bounds["min_lat"]
    max_lat = bounds["max_lat"]
    min_lng = bounds["min_lng"]
    max_lng = bounds["max_lng"]
    center_lat = bounds["center_lat"]
    center_lng = bounds["center_lng"]

    base = (backend_url or "").rstrip("/")

    def api_url(path: str) -> str:
        return f"{base}{path}" if base else path

    terrain_image_url = api_url("/api/map/input/terrain-image")
    markers_url = api_url("/api/map/input/markers")
    click_url = api_url("/api/map/input/click")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:100%; height:100%; background:#0b1a2e; }}
  #map {{ width:100%; height:100%; }}

  .ctx-menu {{
    background: #1e293b;
    border: 1px solid rgba(99,130,180,0.3);
    border-radius: 10px;
    padding: 6px;
    min-width: 180px;
    font-family: 'Segoe UI', sans-serif;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }}
  .ctx-title {{
    color: #94a3b8;
    font-size: 11px;
    padding: 4px 10px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 4px;
  }}
  .ctx-btn {{
    display: block;
    width: 100%;
    padding: 8px 12px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: #e2e8f0;
    font-size: 13px;
    text-align: left;
    border-radius: 6px;
    transition: background 0.15s;
  }}
  .ctx-btn:hover {{ background: rgba(59,130,246,0.25); }}

  .leaflet-popup-content-wrapper {{
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    padding: 0 !important;
  }}
  .leaflet-popup-tip-container {{ display: none !important; }}
  .leaflet-popup-content {{ margin: 0 !important; }}

  .map-badge {{
    background: rgba(15, 23, 42, 0.88);
    color: #e2e8f0;
    border: 1px solid rgba(148,163,184,0.18);
    border-radius: 10px;
    padding: 8px 12px;
    font: 600 12px/1.45 'Segoe UI', sans-serif;
    box-shadow: 0 8px 24px rgba(0,0,0,0.28);
  }}
</style>
</head>
<body>
<div id="map"></div>
<script>
(function() {{
  var BOUNDS = [
    [{min_lat:.6f}, {min_lng:.6f}],
    [{max_lat:.6f}, {max_lng:.6f}]
  ];

  var map = L.map('map', {{
    zoomControl: true,
    attributionControl: false,
    preferCanvas: true,
    maxBounds: BOUNDS,
    maxBoundsViscosity: 0.85
  }}).setView([{center_lat:.6f}, {center_lng:.6f}], 14);

  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 18,
    opacity: 0.32
  }}).addTo(map);

  L.imageOverlay('{terrain_image_url}?_t=' + Date.now(), BOUNDS, {{
    opacity: 0.92,
    interactive: false
  }}).addTo(map);

  L.rectangle(BOUNDS, {{
    color: '#60a5fa',
    weight: 1,
    opacity: 0.55,
    fill: false
  }}).addTo(map);

  map.fitBounds(BOUNDS, {{padding:[8,8]}});

  var badge = L.control({{position: 'bottomleft'}});
  badge.onAdd = function() {{
    var div = L.DomUtil.create('div', 'map-badge');
    div.innerHTML = '<b>작전 지역</b><br>backend/data/map/static parquet';
    return div;
  }};
  badge.addTo(map);

  function makePinIcon(fillColor) {{
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">' +
      '<path d="M14 0C6.27 0 0 6.27 0 14 0 24.5 14 38 14 38S28 24.5 28 14C28 6.27 21.73 0 14 0Z"' +
      ' fill="' + fillColor + '"/>' +
      '<circle cx="14" cy="14" r="6" fill="white"/>' +
      '</svg>';
    return L.divIcon({{
      html: svg,
      iconSize: [28, 38],
      iconAnchor: [14, 38],
      popupAnchor: [0, -40],
      className: ''
    }});
  }}

  var BLUE_ICON = makePinIcon('#3b82f6');
  var RED_ICON = makePinIcon('#ef4444');
  var markers = {{}};

  function refreshMarkers(list) {{
    Object.keys(markers).forEach(function(k) {{
      map.removeLayer(markers[k]);
    }});
    markers = {{}};

    (list || []).forEach(function(m) {{
      if (m.lat == null || m.lng == null) return;
      var kind = m.kind || m.type || 'arrival';
      var mkey = m.id || (kind === 'departure' ? 'departure' : ('unit' + (m.unit || '?')));
      var icon = kind === 'departure' ? RED_ICON : BLUE_ICON;
      var label = kind === 'departure' ? '출발지' : ((m.unit || '?') + '제대 도착지');
      markers[mkey] = L.marker([m.lat, m.lng], {{icon: icon}})
        .bindTooltip(label, {{permanent: true, direction: 'top', offset: [0, -40]}})
        .addTo(map);
    }});
  }}

  var lastMarkerSeq = -1;
  (function pollMarkers() {{
    fetch('{markers_url}')
      .then(function(r) {{ return r.json(); }})
      .then(function(d) {{
        if (d.seq !== lastMarkerSeq) {{
          lastMarkerSeq = d.seq;
          refreshMarkers(d.markers || []);
        }}
      }})
      .catch(function() {{}});
    setTimeout(pollMarkers, 100);
  }})();

  var ctxPopup = null;

  map.on('contextmenu', function(e) {{
    var lat = e.latlng.lat.toFixed(6);
    var lng = e.latlng.lng.toFixed(6);

    var html =
      '<div class="ctx-menu">' +
      '<div class="ctx-title">' + lat + ', ' + lng + '</div>' +
      '<button class="ctx-btn" onclick="selectUnit(0,' + lat + ',' + lng + ')">&#128205; 출발지로 설정</button>' +
      '<button class="ctx-btn" onclick="selectUnit(1,' + lat + ',' + lng + ')">&#128205; 1제대 도착지로 설정</button>' +
      '<button class="ctx-btn" onclick="selectUnit(2,' + lat + ',' + lng + ')">&#128205; 2제대 도착지로 설정</button>' +
      '<button class="ctx-btn" onclick="selectUnit(3,' + lat + ',' + lng + ')">&#128205; 3제대 도착지로 설정</button>' +
      '</div>';

    if (ctxPopup) map.closePopup(ctxPopup);
    ctxPopup = L.popup({{closeButton: false, maxWidth: 220, className: 'ctx-popup'}})
      .setLatLng(e.latlng)
      .setContent(html)
      .openOn(map);
  }});

  window.selectUnit = function(unit, lat, lng) {{
    if (ctxPopup) {{ map.closePopup(ctxPopup); ctxPopup = null; }}
    var kind = (unit === 0) ? 'departure' : 'arrival';
    fetch('{click_url}', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        unit: unit,
        lat: parseFloat(lat),
        lng: parseFloat(lng),
        kind: kind,
        departure: unit === 0
      }})
    }}).catch(function() {{}});
  }};

  map.on('click', function() {{
    if (ctxPopup) {{ map.closePopup(ctxPopup); ctxPopup = null; }}
  }});
}})();
</script>
</body>
</html>"""


@router.get("/html", response_class=HTMLResponse, include_in_schema=False)
async def get_input_map_html():
    """입력용 인터랙티브 지도 HTML (iframe src로 직접 로드)."""
    return HTMLResponse(content=_build_input_map_html())


@router.get("/terrain-image", include_in_schema=False)
async def get_input_terrain_image():
    """backend/data/map/static parquet 기반 정적 지형 PNG."""
    try:
        return Response(content=_generate_input_terrain_png_bytes(), media_type="image/png")
    except Exception:
        logger.exception("입력 지도 terrain 이미지 생성 실패")
        return Response(status_code=500, media_type="image/png")


def build_input_map_html(backend_url: str) -> str:
    """
    프론트엔드 srcdoc/절대 경로 호환용 입력 맵 HTML 반환.
    backend_url 예: http://localhost:8000
    """
    return _build_input_map_html(backend_url)


# ── 마커 API ─────────────────────────────────────────────

class MarkerItem(BaseModel):
    id: str | None = None
    unit: int | None = None
    lat: float
    lng: float
    type: str | None = None
    kind: str | None = None
    departure: bool = False


class MarkersPayload(BaseModel):
    seq: int | None = None
    markers: list[MarkerItem]


@router.get("/markers", summary="현재 마커 목록 조회 (지도 폴링용)")
async def get_markers():
    return {"seq": _marker_seq, "markers": _markers}


@router.post("/markers", summary="마커 업데이트 (Solara → 지도)")
async def set_markers(payload: MarkersPayload):
    global _marker_seq, _markers, _last_marker_client_seq
    client_seq = payload.seq or 0
    if client_seq and client_seq < _last_marker_client_seq:
        return {"ok": True, "seq": _marker_seq, "ignored": True}

    if client_seq:
        _last_marker_client_seq = client_seq
    _marker_seq += 1
    next_markers = []
    for index, marker in enumerate(payload.markers, start=1):
        kind = marker.kind or marker.type or ("departure" if marker.departure else "arrival")
        unit = 0 if kind == "departure" and marker.unit is None else marker.unit
        marker_id = marker.id or ("departure" if kind == "departure" else f"target-{unit or index}")
        next_markers.append({
            "id": marker_id,
            "unit": unit,
            "lat": marker.lat,
            "lng": marker.lng,
            "type": kind,
            "kind": kind,
            "departure": kind == "departure",
        })
    _markers = next_markers
    return {"ok": True, "seq": _marker_seq}


# ── 클릭 이벤트 API ───────────────────────────────────────

class ClickPayload(BaseModel):
    unit: int | None = None
    lat: float
    lng: float
    kind: str = "arrival"   # "arrival" | "departure"
    departure: bool = False


@router.post("/click", summary="우클릭 지점 기록 (지도 → 백엔드)")
async def record_click(payload: ClickPayload):
    global _click_seq, _pending_clicks
    _click_seq += 1
    kind = "departure" if payload.departure or payload.kind == "departure" or payload.unit == 0 else "arrival"
    unit = 0 if kind == "departure" else payload.unit
    _pending_clicks.append({
        "seq": _click_seq,
        "unit": unit,
        "lat": payload.lat,
        "lng": payload.lng,
        "kind": kind,
        "departure": kind == "departure",
    })
    return {"ok": True, "seq": _click_seq}


@router.get("/pending-click", summary="미처리 클릭 조회 (Solara 폴링용)")
async def get_pending_click():
    if not _pending_clicks:
        return {"seq": 0, "unit": None, "lat": None, "lng": None, "kind": None, "departure": False}
    return _pending_clicks.pop(0)
