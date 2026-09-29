import pytest

from src import db
from src.config import load_app_config


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_schema(c)
    yield c
    c.close()


def test_fts5_available():
    assert db.fts5_available()


def test_init_schema_is_idempotent(conn):
    db.init_schema(conn)
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"pois", "poi_fts", "meta"} <= names


def test_meta_roundtrip(conn):
    assert db.get_meta(conn, "dataset_version") is None
    db.set_meta(conn, "dataset_version", "v1")
    db.set_meta(conn, "dataset_version", "v2")
    assert db.get_meta(conn, "dataset_version") == "v2"


def test_bm25_sql_follows_fts_column_order():
    weights = {"tags": 0.5, "name": 2, "description": 1, "category": 1.5}
    assert db.bm25_sql(weights) == "bm25(poi_fts, 0.0, 2.0, 1.5, 1.0, 0.5)"


def test_bm25_smaller_score_is_better_match(conn):
    # Dữ liệu tổng hợp. Từ truy vấn chỉ nằm trong 2/6 tài liệu để IDF dương:
    # FTS5 kẹp IDF về gần 0 khi một từ xuất hiện trong hơn nửa corpus.
    docs = [
        ("a", "van phong pham hong ha", "van phong pham", "", ""),
        ("b", "tiem photocopy", "van phong pham", "in tai lieu nhieu loai giay van phong pham", ""),
        ("c", "com tam", "an uong", "", ""),
        ("d", "pho bo", "an uong", "", ""),
        ("e", "tra sua", "an uong", "", ""),
        ("f", "circle k", "tien loi", "", ""),
    ]
    conn.executemany(
        "INSERT INTO poi_fts(poi_id, name, category, description, tags) VALUES (?, ?, ?, ?, ?)", docs
    )
    weights = load_app_config()["ranking"]["bm25_column_weights"]
    rows = conn.execute(
        f"SELECT poi_id, {db.bm25_sql(weights)} AS score FROM poi_fts "
        "WHERE poi_fts MATCH ? ORDER BY score",
        ('"van" "phong" "pham"',),
    ).fetchall()

    assert [r["poi_id"] for r in rows] == ["a", "b"]
    assert all(r["score"] < 0 for r in rows)
