"""
frontend/components/map_html_builder.py

Leaflet 지도 HTML 빌더 — Solara 컴포넌트 컨텍스트와 완전히 격리된 순수 Python 모듈.
이 파일은 @solara.component 데코레이터를 일절 사용하지 않음.

백엔드 이미지 오버레이:
  /api/map/tactical/terrain-image        — lc_code 기반 지형 색상 PNG
  /api/map/tactical/buffer-image         — 경로 버퍼 마스크 PNG
  /api/map/tactical/cost-image?layer=X   — 위험도/기동성/센서 비용 레이어 PNG
"""

from __future__ import annotations


# 지도 고정 경계 (parquet 실측값, WGS84)
_MAP_BOUNDS = {
    "min_lat": 54.2977,
    "max_lat": 54.5209,
    "min_lng": 18.2640,
    "max_lng": 18.6479,
}

# 탭명 → API layer 파라미터 매핑
_LAYER_MAP: dict[str, str] = {
    "종합상황도": "risk",
    "기동상황도": "mobility",
    "센서상황도": "sensor",
}


def build_base_map_html(backend_url: str, selected_layer: str = "종합상황도") -> str:
    """
    지형 PNG + 버퍼 오버레이 + 비용 레이어 Leaflet HTML 문자열 반환.

    backend_url     : 예) "http://127.0.0.1:8000"
    selected_layer  : "종합상황도" | "기동상황도" | "센서상황도"
    """
    b = _MAP_BOUNDS
    center_lat = (b["min_lat"] + b["max_lat"]) / 2
    center_lng = (b["min_lng"] + b["max_lng"]) / 2
    layer_key  = _LAYER_MAP.get(selected_layer, "risk")

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
  .legend {{
    background: rgba(15,25,50,0.88);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px; padding: 8px 12px;
    color: #e2e8f0; font-size: 11px; line-height: 1.8;
    pointer-events: none;
  }}
  .dot {{ display:inline-block; width:10px; height:10px;
          border-radius:50%; margin-right:4px; vertical-align:middle; }}
  .grad-bar {{
    width: 100px; height: 10px; border-radius: 3px;
    background: linear-gradient(to right, rgba(0,180,0,0.7), rgba(220,220,0,0.7), rgba(220,0,0,0.9));
    display: inline-block; vertical-align: middle; margin: 0 4px;
  }}
</style>
</head>
<body>
<div id="map"></div>
<script>
(function() {{
  var BACKEND = '{backend_url}';
  var bounds = [
    [{b["min_lat"]:.6f}, {b["min_lng"]:.6f}],
    [{b["max_lat"]:.6f}, {b["max_lng"]:.6f}]
  ];

  var map = L.map('map', {{
    zoomControl: true,
    attributionControl: false,
    preferCanvas: true
  }}).setView([{center_lat:.5f}, {center_lng:.5f}], 10);

  // 베이스 타일
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 18, opacity: 0.5
  }}).addTo(map);

  // 1) 지형 레이어 (lc_code 색상 PNG)
  L.imageOverlay(
    BACKEND + '/api/map/tactical/terrain-image',
    bounds,
    {{ opacity: 0.70, interactive: false }}
  ).addTo(map);

  // 2) TIF 버퍼 레이어 (route_buffer_mask — 황색 반투명)
  L.imageOverlay(
    BACKEND + '/api/map/tactical/buffer-image',
    bounds,
    {{ opacity: 0.50, interactive: false }}
  ).addTo(map);

  // 3) 비용 레이어 (위험도 / 기동성 / 센서) — 초기값은 Python에서 embed
  var costLayer = L.imageOverlay(
    BACKEND + '/api/map/tactical/cost-image?layer={layer_key}&_t=' + Date.now(),
    bounds,
    {{ opacity: 0.78, interactive: false }}
  ).addTo(map);

  map.fitBounds(bounds, {{ padding: [8, 8] }});

  // ── postMessage 핸들러 ─────────────────────────────────
  var mks = {{}};

  function makeIcon(c) {{
    return L.divIcon({{
      html: '<div style="background:'+c+';width:16px;height:16px;border-radius:50%;' +
            'border:2.5px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.6);"></div>',
      iconSize: [16,16], iconAnchor: [8,8], className: ''
    }});
  }}

  window.addEventListener('message', function(e) {{
    if (!e.data) return;

    // 마커 업데이트
    if (e.data.type === 'setMarkers') {{
      e.data.markers.forEach(function(m) {{
        if (mks[m.id]) map.removeLayer(mks[m.id]);
        var lat = parseFloat(m.lat), lng = parseFloat(m.lng);
        if (!isNaN(lat) && !isNaN(lng)) {{
          mks[m.id] = L.marker([lat, lng], {{ icon: makeIcon(m.color || '#e67e22') }})
            .bindTooltip(m.label || m.id, {{
              permanent: true, direction: 'top', offset: [0, -12]
            }})
            .addTo(map);
        }}
      }});
    }}

    // 레이어 교체 (postMessage로도 전환 가능)
    if (e.data.type === 'setLayer') {{
      map.removeLayer(costLayer);
      costLayer = L.imageOverlay(
        BACKEND + '/api/map/tactical/cost-image?layer=' + e.data.layer + '&_t=' + Date.now(),
        bounds,
        {{ opacity: 0.78, interactive: false }}
      ).addTo(map);
    }}
  }});
}})();
</script>
</body>
</html>"""


def build_input_map_html(backend_url: str) -> str:
    """
    작전 지역 입력 페이지용 인터랙티브 Leaflet 지도 HTML.
    - 우클릭 → parent.postMessage({type:'coordClick', unit, lat, lng})
    - parent → window.addEventListener('message', setMarkers) → 마커 표시
    - 백엔드 API 불필요 (srcdoc null-origin CORS 문제 없음)
    - 전술 오버레이(이미지)는 백엔드 있을 때만 표시
    """
    b = _MAP_BOUNDS
    api = backend_url  # 전술 오버레이 이미지용 (fetch 아닌 <img> → CORS 무관)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:100%; height:100%; background:#0b1a2e; }}
  #map {{ width:100%; height:100%; }}
  .ctx-menu {{
    background:#1e293b; border:1px solid rgba(99,130,180,0.35);
    border-radius:10px; padding:6px; min-width:195px;
    font-family:'Segoe UI',sans-serif; box-shadow:0 4px 20px rgba(0,0,0,0.55);
  }}
  .ctx-title {{
    color:#94a3b8; font-size:11px; padding:4px 10px 6px;
    border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:4px;
  }}
  .ctx-btn {{
    display:block; width:100%; padding:8px 12px;
    background:transparent; border:none; cursor:pointer;
    color:#e2e8f0; font-size:13px; text-align:left; border-radius:6px;
  }}
  .ctx-btn:hover {{ background:rgba(59,130,246,0.25); }}
  .leaflet-popup-content-wrapper {{
    background:transparent!important; box-shadow:none!important;
    border:none!important; padding:0!important;
  }}
  .leaflet-popup-tip-container {{ display:none!important; }}
  .leaflet-popup-content {{ margin:0!important; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
(function() {{
  var BOUNDS = [[{b["min_lat"]:.6f},{b["min_lng"]:.6f}],[{b["max_lat"]:.6f},{b["max_lng"]:.6f}]];
  var API    = '{api}';

  var map = L.map('map', {{zoomControl:true, attributionControl:false, preferCanvas:true}})
              .fitBounds(BOUNDS, {{padding:[4,4]}});

  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom:18, opacity:0.6
  }}).addTo(map);

  // 전술 오버레이 — <img> 로드이므로 CORS 불필요, 백엔드 없으면 조용히 스킵
  function tryOverlay(url, opacity) {{
    var img = new Image();
    img.onload = function() {{
      L.imageOverlay(url, BOUNDS, {{opacity:opacity, interactive:false}}).addTo(map);
    }};
    img.src = url;
  }}
  tryOverlay(API+'/api/map/tactical/terrain-image', 0.65);
  tryOverlay(API+'/api/map/tactical/buffer-image',  0.45);
  tryOverlay(API+'/api/map/tactical/cost-image?layer=risk&_t='+Date.now(), 0.72);

  // 핀 아이콘
  function pin(color) {{
    var s='<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">'
        +'<path d="M14 0C6.27 0 0 6.27 0 14 0 24.5 14 38 14 38S28 24.5 28 14C28 6.27 21.73 0 14 0Z"'
        +' fill="'+color+'" stroke="rgba(255,255,255,0.6)" stroke-width="1.5"/>'
        +'<circle cx="14" cy="14" r="5.5" fill="white"/></svg>';
    return L.divIcon({{html:s, iconSize:[28,38], iconAnchor:[14,38], popupAnchor:[0,-40], className:''}});
  }}
  var BLUE=pin('#3b82f6'), RED=pin('#ef4444');

  // 마커 관리 — parent로부터 setMarkers postMessage 수신
  var mks={{}};
  function refreshMarkers(list) {{
    Object.keys(mks).forEach(function(k){{map.removeLayer(mks[k]);}});
    mks={{}};
    (list||[]).forEach(function(m) {{
      if(m.lat==null||m.lng==null) return;
      // kind 또는 type 필드 모두 지원 (하위 호환)
      var kind = m.kind || m.type || 'arrival';
      var key  = kind==='departure' ? 'departure' : 'unit'+(m.unit||m.id||'?');
      var icon = kind==='departure' ? RED : BLUE;
      var lbl  = kind==='departure' ? '출발지' : ((m.unit||'?')+'제대 도착지');
      mks[key] = L.marker([m.lat,m.lng],{{icon:icon}})
        .bindTooltip(lbl,{{permanent:true,direction:'top',offset:[0,-40]}})
        .addTo(map);
    }});
  }}

  // parent → 지도: setMarkers 수신
  window.addEventListener('message', function(e) {{
    if (!e.data) return;
    if (e.data.type === 'setMarkers') {{
      refreshMarkers(e.data.markers || []);
    }}
  }});

  // 우클릭 컨텍스트 메뉴
  var ctxP=null;
  map.on('contextmenu',function(e){{
    var lat=e.latlng.lat.toFixed(6), lng=e.latlng.lng.toFixed(6);
    var h='<div class="ctx-menu"><div class="ctx-title">위도 '+lat+' / 경도 '+lng+'</div>'
        +'<button class="ctx-btn" onclick="sel(0,'+lat+','+lng+',\'departure\')">📍 출발지로 설정</button>'
        +'<button class="ctx-btn" onclick="sel(1,'+lat+','+lng+',\'arrival\')">📍 1제대 도착지로 설정</button>'
        +'<button class="ctx-btn" onclick="sel(2,'+lat+','+lng+',\'arrival\')">📍 2제대 도착지로 설정</button>'
        +'<button class="ctx-btn" onclick="sel(3,'+lat+','+lng+',\'arrival\')">📍 3제대 도착지로 설정</button>'
        +'</div>';
    if(ctxP) map.closePopup(ctxP);
    ctxP=L.popup({{closeButton:false,maxWidth:220}}).setLatLng(e.latlng).setContent(h).openOn(map);
  }});

  // 지도 → parent: coordClick postMessage (kind 포함)
  window.sel=function(unit,lat,lng,kind){{
    if(ctxP){{map.closePopup(ctxP);ctxP=null;}}
    window.parent.postMessage({{
      type:'coordClick', unit:unit,
      lat:parseFloat(lat), lng:parseFloat(lng),
      kind:kind||'arrival'
    }}, '*');
  }};

  map.on('click',function(){{if(ctxP){{map.closePopup(ctxP);ctxP=null;}}}});
}})();
</script>
</body>
</html>"""
