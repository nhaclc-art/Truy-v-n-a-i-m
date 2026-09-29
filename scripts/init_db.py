"""Kiểm tra FTS5 và tạo schema SQLite (chạy lặp an toàn). Dữ liệu POI nạp bằng bước import."""
import sqlite3
import sys

from scripts import use_utf8_stdio
from src import db
from src.config import ROOT


def main() -> int:
    if not db.fts5_available():
        print(f"LỖI: SQLite {sqlite3.sqlite_version} của Python này không hỗ trợ FTS5.", file=sys.stderr)
        return 1
    conn = db.connect()
    try:
        db.init_schema(conn)
        poi_count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
        version = db.get_meta(conn, "dataset_version", "chưa import")
    finally:
        conn.close()
    print(f"SQLite {sqlite3.sqlite_version}, FTS5: có")
    print(f"DB: {db.DEFAULT_DB_PATH.relative_to(ROOT)}")
    print(f"Số POI: {poi_count}; dataset_version: {version}")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
