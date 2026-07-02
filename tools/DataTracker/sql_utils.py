from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"


def load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")
