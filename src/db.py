"""Schema SQLite: bảng POI hiển thị, chỉ mục FTS5 trên văn bản đã chuẩn hóa và bảng meta."""
import sqlite3
from pathlib import Path

from src.config import ROOT

DEFAULT_DB_PATH = ROOT / "data" / "georank.db"

# Thứ tự cột quyết định thứ tự trọng số trong bm25(); poi_id là cột UNINDEXED.
FTS_COLUMNS = ("poi_id", "name", "category", "description", "tags")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pois (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    address TEXT,
    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    description TEXT,
    tags TEXT,
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    retrieved_at TEXT,
    verification_status TEXT NOT NULL
        CHECK (verification_status IN ('source_only', 'cross_checked', 'field_checked')),
    verified_at TEXT,
    verification_note TEXT,
    listing_url TEXT,
    listing_checked_at TEXT,
    opening_hours TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS poi_fts USING fts5(
    poi_id UNINDEXED,
    name,
    category,
    description,
    tags,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE probe USING fts5(body)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def bm25_sql(weights: dict[str, float]) -> str:
    """Biểu thức bm25() theo đúng thứ tự cột FTS. Giá trị càng nhỏ (càng âm) càng khớp."""
    args = [0.0] + [float(weights[col]) for col in FTS_COLUMNS[1:]]
    return f"bm25(poi_fts, {', '.join(repr(w) for w in args)})"
