
# PostgreSQL 붙일 자리

현재 프로젝트는 FastAPI 진입점(`backend/app/main.py`)과 시뮬레이션 API(`backend/app/api/simulation.py`)가 이미 분리되어 있으므로,
DB는 아래 순서로 얹으면 됩니다.

1. `.env.example` 을 복사해서 `.env` 생성
2. PostgreSQL 실행 후 `DATABASE_URL` 설정
3. `backend/app/db/sql/10_schema.sql` 에 팀원이 작성한 CREATE TABLE 붙여넣기
4. 필요 시 `backend/app/db/sql/20_indexes.sql` 에 인덱스 추가
5. 아래 명령으로 초기화

```bash
python -m app.db.init_db
```

## 권장 후속 작업
- `simulation_service.py` 안에서 run 생성/조회 함수 연결
- `api/simulation.py` 에 run_id 기반 REST 엔드포인트 확장
- 프론트 `frontend/services/api_client.py` 에 DB 기반 조회 API 추가
