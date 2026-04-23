# 파이브웨더즈 UGV 전술 지원 시스템

전술 UGV 실시간 의사결정 지원 대시보드.  
FastAPI 백엔드 + Solara 프론트엔드 구성.

---

## 폴더 구조

```
claude/
├── backend/          # FastAPI 서버
│   ├── app/
│   │   ├── api/          # REST + WebSocket 엔드포인트
│   │   ├── core/         # 설정, 보안, 로깅, WS 매니저
│   │   ├── db/           # ORM 모델, 스키마, 세션
│   │   ├── services/     # 비즈니스 로직
│   │   └── simulation/
│   │       ├── mock/         # 더미 시뮬레이터 (개발용)
│   │       ├── adapters/     # 실 알고리즘 연결 인터페이스
│   │       ├── loaders/      # 데이터 레이어 로더
│   │       └── runtime/      # 상태머신, 큐, 재계획 엔진
│   ├── scripts/      # DB 초기 데이터 로드 스크립트
│   ├── create_admin.py   # 관리자 계정 수동 복구 스크립트
│   ├── .env.example  # 환경변수 예시
│   ├── requirements.txt
│   └── docker-compose.yml
├── frontend/         # Solara 프론트엔드
│   ├── app.py            # 메인 진입점 (4페이지 라우팅)
│   ├── components/       # UI 컴포넌트
│   ├── services/         # API 클라이언트, 상태 관리
│   └── state.py          # 전역 reactive 상태
└── docs/             # 개발 중 생성된 참고 파일
```

---

## 실행 방법

### 사전 요구사항
- Python 3.11+
- PostgreSQL 16 실행 중

### 1. 백엔드

```bash
cd backend

# 가상환경 생성 및 패키지 설치
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

# 환경변수 설정
copy .env.example .env          # Windows
# cp .env.example .env          # Mac/Linux
# .env 파일 열어서 실제 값 입력

# 서버 실행
uvicorn app.main:app --reload
```

백엔드 주소: http://localhost:8000  
API 문서: http://localhost:8000/docs

### 2. 프론트엔드

```bash
cd frontend

python -m venv .venv
.venv\Scripts\activate
pip install solara starlette==0.45.3 ipyleaflet ipywidgets websocket-client

solara run app.py
```

프론트엔드 주소: http://localhost:8765

---

## 환경변수 설정

`backend/.env.example`을 `backend/.env`로 복사 후 아래 항목 필수 입력:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 주소 | `postgresql+asyncpg://postgres:pass@localhost:5432/fiveweathersDB` |
| `JWT_SECRET_KEY` | JWT 서명 키 (충분히 긴 랜덤 값) | `openssl rand -hex 32` 결과 |
| `ADMIN_USERNAME` | 초기 관리자 아이디 | `user1` |
| `ADMIN_PASSWORD` | 초기 관리자 비밀번호 | `user1` |

---

## 계정 복구

백엔드 시작 시 자동으로 admin 계정이 생성되지만, 실패한 경우:

```bash
cd backend
.venv\Scripts\activate
python create_admin.py --username user1 --password user1
```

---

## 모드 구분

| 모드 | 설명 |
|------|------|
| **Mock 모드** (현재) | `backend/app/simulation/mock/dummy_runner.py`가 가짜 데이터 생성. 알고리즘 없이 UI/API 연동 검증 가능 |
| **Real 모드** (예정) | `backend/app/simulation/adapters/`의 실 알고리즘 어댑터로 교체. `orchestrator.py`에서 분기 |

현재는 **Mock 모드**로 동작합니다.  
`orchestrator.py`의 `run_simulation()` 함수에서 `dummy_runner` → 실 어댑터로 교체하면 Real 모드 전환 가능.

---

## Docker로 실행 (백엔드 + DB)

```bash
cd backend
docker compose up -d
```

---

## 페이지 플로우

1. **로그인** — 아이디/비밀번호 입력
2. **임무 변수 입력** — UGV 수, 성공률 기준, 정찰구역 수 등
3. **경로 계획 확인** — A/B/C 경로 지도 + 파레토 분석, 경로 선택
4. **메인 대시보드** — 실시간 KPI, 대기열, 지도, LTWR 현황
