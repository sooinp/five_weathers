"""
backend/app/api/sim_video.py

시뮬레이션 결과 영상(MP4) 관리 API.

흐름:
  영상 파일 준비 → POST /api/map/video/upload → 저장
  프론트(video 태그) → /sim-videos/current.mp4 로 표시

엔드포인트 (prefix: /api):
  POST   /api/map/video/upload  — MP4 파일 업로드 (multipart)
  GET    /api/map/video/status  — 현재 파일 존재 여부 + 업로드 시각
  DELETE /api/map/video/clear   — 업로드된 파일 삭제

MP4 파일은 /sim-videos/current.mp4 로 StaticFiles 서빙.
프론트에서는 <video src="/sim-videos/current.mp4"> 방식으로 임베드.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/map/video", tags=["sim-video"])

SIM_VIDEO_DIR  = Path(__file__).resolve().parents[2] / "data" / "sim_video"
CURRENT_VIDEO  = SIM_VIDEO_DIR / "current.mp4"
PLAYER_HTML    = SIM_VIDEO_DIR / "player.html"
CURRENT_URL    = "/sim-videos/current.mp4"
PLAYER_URL     = "/sim-videos/player.html"

_PLAYER_HTML_CONTENT = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #000; overflow: hidden; }
  video { width: 100%; height: 100%; object-fit: contain; display: block; }
</style>
</head>
<body>
  <video id="v" muted preload="auto">
    <source src="./current.mp4" type="video/mp4">
  </video>
  <script>
    var vid = document.getElementById('v');
    var params = new URLSearchParams(window.location.search);
    var shouldPlay = params.get('play') === '1';

    // 자동 재생 방지 (play=0 또는 파라미터 없을 때)
    vid.pause();

    vid.addEventListener('loadedmetadata', function() {
      vid.currentTime = 0.001;
      if (!shouldPlay) {
        vid.pause();
      }
    });

    vid.addEventListener('ended', function() { vid.pause(); });

    if (shouldPlay) {
      // play=1: 재생 가능 상태가 되면 즉시 재생 시작
      vid.addEventListener('canplay', function onCanPlay() {
        vid.removeEventListener('canplay', onCanPlay);
        vid.currentTime = 0;
        var p = vid.play();
        if (p !== undefined) {
          p.catch(function(e) { console.warn('video play blocked:', e); });
        }
      });
    }
  </script>
</body>
</html>
"""

_uploaded_at: datetime | None = None

# ── 재생 제어 상태 ────────────────────────────────────────
_cmd: str = "idle"   # "idle" | "play" | "stop"
_cmd_key: int = 0    # 명령이 바뀔 때마다 증가 → player.html이 변경 감지


def _ensure_dir():
    SIM_VIDEO_DIR.mkdir(parents=True, exist_ok=True)


# ── 재생 제어 ─────────────────────────────────────────────

@router.post("/command", summary="영상 재생 제어 명령 (play/stop)")
async def set_video_command(cmd: str):
    """cmd: 'play' 또는 'stop'"""
    global _cmd, _cmd_key
    if cmd not in ("play", "stop"):
        raise HTTPException(status_code=422, detail="cmd must be 'play' or 'stop'")
    _cmd_key += 1
    _cmd = cmd
    return {"ok": True, "cmd": _cmd, "key": _cmd_key}


@router.get("/command", summary="영상 재생 제어 상태 조회")
async def get_video_command():
    """player.html 폴링용 — 현재 명령과 키를 반환 (캐시 방지 헤더 포함)."""
    return JSONResponse(
        content={"cmd": _cmd, "key": _cmd_key},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


# ── 업로드 ────────────────────────────────────────────────

@router.post("/upload", summary="시뮬레이션 결과 영상(MP4) 업로드")
async def upload_sim_video(request: Request):
    """
    영상 파일을 받아 current.mp4 로 저장.

    두 가지 방식 모두 지원:
      1) multipart/form-data  — field name: file
      2) raw body             — Content-Type: video/mp4 로 직접 전송
    """
    global _uploaded_at
    _ensure_dir()

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload: UploadFile = form.get("file")
        if upload is None:
            raise HTTPException(status_code=422, detail="form field 'file' 필요")
        video_bytes = await upload.read()
    else:
        video_bytes = await request.body()

    if not video_bytes:
        raise HTTPException(status_code=422, detail="빈 파일입니다.")

    # 최소 크기 검증 (MP4 시그니처: ftyp box 확인)
    if len(video_bytes) < 8:
        raise HTTPException(status_code=422, detail="유효하지 않은 영상 파일입니다.")

    CURRENT_VIDEO.write_bytes(video_bytes)
    PLAYER_HTML.write_text(_PLAYER_HTML_CONTENT, encoding="utf-8")  # 플레이어 HTML 갱신
    _uploaded_at = datetime.now(timezone.utc)

    size_mb = len(video_bytes) / (1024 * 1024)
    logger.info("sim_video uploaded: %.2f MB at %s", size_mb, _uploaded_at.isoformat())
    return {
        "ok": True,
        "url": CURRENT_URL,
        "player_url": PLAYER_URL,
        "size_bytes": len(video_bytes),
        "size_mb": round(size_mb, 2),
        "uploaded_at": _uploaded_at.isoformat(),
    }


# ── 상태 조회 ─────────────────────────────────────────────

@router.get("/status", summary="업로드 영상 상태 조회")
async def get_sim_video_status():
    """현재 업로드된 MP4 파일과 player.html 존재 여부 반환."""
    video_exists  = CURRENT_VIDEO.exists()
    player_exists = PLAYER_HTML.exists()
    # player.html 없으면 자동 생성 (서버 재시작 후에도 영상이 있으면 즉시 표시)
    if video_exists and not player_exists:
        _ensure_dir()
        PLAYER_HTML.write_text(_PLAYER_HTML_CONTENT, encoding="utf-8")
        player_exists = True
    available = video_exists and player_exists
    size = CURRENT_VIDEO.stat().st_size if video_exists else None
    return {
        "available":    available,
        "url":          CURRENT_URL if available else None,
        "player_url":   PLAYER_URL  if available else None,
        "uploaded_at":  _uploaded_at.isoformat() if _uploaded_at else None,
        "size_bytes":   size,
        "size_mb":      round(size / (1024 * 1024), 2) if size else None,
    }


# ── 삭제 ─────────────────────────────────────────────────

@router.delete("/clear", summary="업로드된 MP4 삭제")
async def clear_sim_video():
    """저장된 current.mp4 및 player.html 삭제 (초기화)."""
    global _uploaded_at
    if CURRENT_VIDEO.exists():
        CURRENT_VIDEO.unlink()
    if PLAYER_HTML.exists():
        PLAYER_HTML.unlink()
    _uploaded_at = None
    return {"ok": True, "message": "영상 삭제 완료"}
