from pathlib import Path
from sqlalchemy import text
from app.db.session import engine

SQL_DIR = Path(__file__).resolve().parent / "sql"

def run_sql_file(path: Path) -> None:
    sql_text = path.read_text(encoding="utf-8")
    if not sql_text.strip():
        return

    with engine.begin() as conn:
        conn.execute(text(sql_text))

def init_db() -> None:
    for path in sorted(SQL_DIR.glob("*.sql")):
        run_sql_file(path)

if __name__ == "__main__":
    init_db()
    print("[OK] database bootstrap SQL executed")
