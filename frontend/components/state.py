import solara

workflowstep = solara.reactive(0)
################# 실행/종료 버튼으로 타이머 역할 하기 ######################

timer_running = solara.reactive(False)
timer_end_ts = solara.reactive(None)
remaining_time_text_global = solara.reactive("02:20:00")
# 가상 잔여 초 — clock_loop이 0.5초마다 600씩 감산 (14틱×0.5s=7s, 14×600=8400)
timer_remaining_secs = solara.reactive(8400)   # 2시간 20분 = 8400초

# 영상 재생 제어 — True: 실행 중 (play), False: 정지
video_should_play = solara.reactive(False)

