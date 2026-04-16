# -----------------------------
# SIMULATION PHYSICS & AP RESOLVER
# -----------------------------
def resolve_tile_entry(
    C_mob_prime: float,
    C_sen_prime: float,
    is_diagonal: bool,
    alpha: float = 0.6,
    ap_min: float = 80_000.0,      # 위험도 0일 때 AP (15 km/h, 200m ≈ 0.8분)
    ap_max: float = 400_000.0,     # 위험도 1일 때 AP (약 3 km/h 근처 느낌, 턴의 ~40%)
    ap_turn: float = 1_000_000.0,  # 턴당 총 AP (참고용, 필요시 사용)
    p: float = 2.0                 # 비선형 지수 (>=1, 클수록 고위험 구간 AP 급증)
):
    """
    C_mob_prime, C_sen_prime : [0, 1] 범위의 정규화된 위험도 성분
                               (block 타일은 이 함수 호출 전에 필터링된다고 가정)
    is_diagonal              : 대각선 이동 여부
    """

    # 1. 통합 위험도 (C_tot') 계산
    normalized_c_total = (alpha * C_mob_prime) + ((1.0 - alpha) * C_sen_prime)
    normalized_c_total = float(np.clip(normalized_c_total, 0.0, 1.0))

    # 2. 비선형 AP 변환: [0,1] → [ap_min, ap_max]
    #    r=0 → ap_min, r=1 → ap_max, 그 사이 r^p 곡선
    r = normalized_c_total
    base_ap = ap_min + (ap_max - ap_min) * (r ** p)

    # 3. 방향 계수 (대각선 이동 보정)
    direction_coeff = 1.4 if is_diagonal else 1.0
    consumed_ap = int(base_ap * direction_coeff)

    return consumed_ap

def resolve_critical_event(C_mob_prime: float, C_sen_prime: float, remaining_ap: int) -> tuple[int, str]:
    # 1. 최대 발생 확률 설정 (팀과 협의하여 조율 가능)
    P_MAX_MOB = 0.20  # 기동성 위험도 1.0일 때 진흙에 빠질 최대 확률 15%
    P_MAX_SEN = 0.15  # 센서 위험도 1.0일 때 시야/통신이 끊길 최대 확률 10%
    
    # 2. 비선형 확률 계산 (위험도의 제곱에 비례)
    prob_mob = P_MAX_MOB * (C_mob_prime ** 2)
    prob_sen = P_MAX_SEN * (C_sen_prime ** 2)
    
    # 3. 주사위 굴리기
    roll_mob = np.random.rand()
    roll_sen = np.random.rand()
    
    # 4. 판정 및 결과 반환
    if roll_mob < prob_mob or roll_sen < prob_sen:
        # 하나라도 이벤트가 터지면 치명적 실패로 간주
        event_reason = "SOS_MOBILITY" if roll_mob < prob_mob else "SOS_SENSOR"
        
        # 만약 둘 다 터졌다면 더 심각한 상태로 보고 싶을 경우
        if (roll_mob < prob_mob) and (roll_sen < prob_sen):
            event_reason = "SOS_COMPLEX_FAILURE"
            
        # 이벤트 발생 시: 남은 AP 전부 차감 (턴 강제 종료), SOS 상태 반환
        consumed_ap = remaining_ap 
        return consumed_ap, event_reason
        
    else:
        # 이벤트 미발생 시: 추가 소모 AP 없음, 정상 상태 반환
        return 0, "NORMAL"



# -----------------------------
# advance_agent(state, path) : 한 칸 이동/상태 업데이트
# -----------------------------
def advance_agent(
    state: dict,
    path: list,
    mob_risk_4d: np.ndarray,
    sen_risk_4d: np.ndarray,
    time_idx: int = 0,
    alpha: float = 0.6,
):
    """
    UGV를 경로(path) 상의 다음 타일로 한 칸 이동시키고 상태를 업데이트하는 함수.

    :param state: UGV의 현재 상태 (dict)
    :param path: 앞으로 가야 할 경로 좌표 리스트 [(y1, x1), (y2, x2), ...]
    :param mob_risk_4d: 기동 위험도 배열 (시간, Y, X)
    :param sen_risk_4d: 센서 위험도 배열 (시간, Y, X)
    :param time_idx: 현재 시뮬레이션 시간 인덱스
    :param alpha: 기동 vs 센서 가중치
    """
    # 1. 도착 확인
    if not path:
        return state, "ARRIVED"

    # 2. 현재 좌표와 다음 좌표 추출
    current_y, current_x = state["position"]
    next_y, next_x = path[0]  # 아직 pop 하지 않고 좌표만 확인

    # 3. 대각선 이동 여부 판단 (여기서 dy, dx 계산)
    dy = abs(next_y - current_y)
    dx = abs(next_x - current_x)
    is_diagonal = (dy == 1 and dx == 1)

    # 4. 다음 타일의 위험도 가져오기
    C_mob = float(mob_risk_4d[time_idx, next_y, next_x])
    C_sen = float(sen_risk_4d[time_idx, next_y, next_x])

    # 5. 타일 진입 판정 (앞서 정의한 함수 호출)
    consumed_ap, event_status = resolve_tile_entry(
        C_mob_prime=C_mob,
        C_sen_prime=C_sen,
        is_diagonal=is_diagonal,
        alpha=alpha
    )

    # 6. UGV 상태(State) 업데이트
    # 이동 완료했으므로 path에서 제거
    path.pop(0)
    state["position"] = (next_y, next_x)

    # AP 정산 (현재 턴에서 쓸 수 있는 AP 차감, 누적 AP 증가)
    state["current_ap"] -= consumed_ap
    state["accumulated_ap"] += consumed_ap

    # 이벤트 결과에 따른 상태 이상 반영
    if event_status == "STUCK_IN_MUD":
        state["status"] = "STUCK"
        # 필요하다면 추가 페널티 로직 (예: 이번 턴 남은 AP 전부 소진 등)
        # state["current_ap"] = 0

    elif event_status == "SENSOR_BLIND":
        state["status"] = "BLIND"
        state["fov"] = 0  # 시야 상실 등 페널티

    else:
        state["status"] = "NORMAL"

    return state, event_status