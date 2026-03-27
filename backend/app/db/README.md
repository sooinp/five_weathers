# DB scaffolding

이 폴더는 팀원이 작성할 PostgreSQL/PostGIS 테이블 정의를 얹기 위한 자리입니다.

## 추천 작업 순서
1. `sql/00_extensions.sql` 에 PostGIS 등 확장 등록
2. `sql/10_schema.sql` 에 CREATE TABLE 문 추가
3. `sql/20_indexes.sql` 에 run_id, cell_id, ugv_id 중심 인덱스 추가
4. 필요하면 ORM 모델은 `app/db/models/` 또는 별도 모듈로 확장

## 현재 포함된 파일
- `base.py`: SQLAlchemy Base
- `session.py`: PostgreSQL 연결 세션
- `init_db.py`: sql 폴더의 SQL을 순서대로 실행

## 주의
기존 `app/models/` 는 Mesa 시뮬레이션 모델 폴더라서, DB ORM 모델과 혼동하지 않도록 `app/db/` 아래를 별도 사용하도록 분리했습니다.
