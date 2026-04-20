import threading
import time

import solara


################# 실행/종료 버튼으로 타이머 역할 하기 ######################

MISSION_TOTAL_SECS = 2 * 3600 + 20 * 60
MISSION_STEP_REAL_SECS = 0.5
MISSION_STEP_SIM_SECS = 600

timer_running = solara.reactive(False)
timer_end_ts = solara.reactive(None)
remaining_time_text_global = solara.reactive("02:20:00")
# 가상 잔여 초 — 0.5초마다 600씩 감산 (14틱×0.5s=7s, 14×600=8400)
timer_remaining_secs = solara.reactive(MISSION_TOTAL_SECS)

# 영상 재생 제어 — True: 실행 중 (play), False: 정지
video_should_play = solara.reactive(False)
video_reload_nonce = solara.reactive(0)

_timer_thread: threading.Thread | None = None
_timer_stop = threading.Event()
_timer_lock = threading.Lock()


def _fmt_hms(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def _sync_remaining_texts(text: str) -> None:
    remaining_time_text_global.set(text)
    try:
        from services import api_client as _ac

        _ac.home_remaining_time.set(text)
        _ac.time_left.set(text)
    except Exception:
        pass


def _set_timer_state(remaining_secs: int, *, running: bool, play_video: bool) -> None:
    timer_running.set(running)
    timer_end_ts.set(time.time() + remaining_secs if running else None)
    timer_remaining_secs.set(max(0, remaining_secs))
    video_should_play.set(play_video)
    _sync_remaining_texts(_fmt_hms(remaining_secs))


def _stop_existing_timer_thread() -> None:
    global _timer_thread

    _timer_stop.set()
    thread = _timer_thread
    if thread and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=1.5)
    _timer_thread = None
    _timer_stop.clear()


def _timer_loop() -> None:
    try:
        while not _timer_stop.wait(MISSION_STEP_REAL_SECS):
            remaining = max(0, timer_remaining_secs.value - MISSION_STEP_SIM_SECS)
            if remaining <= 0:
                _set_timer_state(0, running=False, play_video=False)
                return
            _set_timer_state(remaining, running=True, play_video=True)
    finally:
        if _timer_stop.is_set():
            _timer_stop.clear()


def start_mission_timer(total_secs: int = MISSION_TOTAL_SECS) -> None:
    global _timer_thread

    with _timer_lock:
        _stop_existing_timer_thread()
        video_reload_nonce.set(video_reload_nonce.value + 1)
        _set_timer_state(total_secs, running=True, play_video=True)
        _timer_thread = threading.Thread(target=_timer_loop, daemon=True)
        _timer_thread.start()


def stop_mission_timer(reset_to_zero: bool = True) -> None:
    remaining = 0 if reset_to_zero else timer_remaining_secs.value
    play_video = False

    with _timer_lock:
        _stop_existing_timer_thread()
        _set_timer_state(remaining, running=False, play_video=play_video)
