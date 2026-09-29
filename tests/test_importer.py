import csv
from pathlib import Path

import pytest

from src import db
from src.importer import POI_FIELDS, import_csv

FIXTURE = Path(__file__).parent / "fixtures" / "pois_fixture.csv"


def read_rows(path: Path = FIXTURE) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict], fields=POI_FIELDS) -> Path:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def match_ids(conn, *tokens: str) -> set[str]:
    query = " ".join(f'"{t}"' for t in tokens)
    return {r["poi_id"] for r in conn.execute("SELECT poi_id FROM poi_fts WHERE poi_fts MATCH ?", (query,))}


def poi_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_schema(c)
    yield c
    c.close()


def test_import_adds_every_row_and_records_version(conn):
    report = import_csv(conn, FIXTURE)

    assert report.errors == []
    assert (report.added, report.updated, report.total) == (6, 0, 6)
    assert report.by_category == {"an_uong": 2, "nha_tro": 1, "tien_loi": 1, "vpp_photocopy": 2}
    assert report.dataset_version.startswith("ds-")
    assert db.get_meta(conn, "dataset_version") == report.dataset_version
    assert conn.execute("SELECT COUNT(*) FROM poi_fts").fetchone()[0] == 6


def test_reimport_same_file_changes_nothing(conn):
    first = import_csv(conn, FIXTURE)
    second = import_csv(conn, FIXTURE)

    assert (second.added, second.updated, second.unchanged) == (0, 0, 6)
    assert second.dataset_version == first.dataset_version
    assert poi_count(conn) == 6


def test_index_holds_normalized_text_with_aliases(conn):
    import_csv(conn, FIXTURE)

    name = conn.execute("SELECT name FROM poi_fts WHERE poi_id = 'fx-vpp-hongha'").fetchone()["name"]
    assert name == "van phong pham hong ha"
    assert match_ids(conn, "dem") == {"fx-com-tam"}
    assert {"fx-vpp-hongha", "fx-photo-ngoclan"} <= match_ids(conn, "van", "phong", "pham")


def test_editing_a_poi_updates_search_without_code_changes(conn, tmp_path):
    import_csv(conn, FIXTURE)
    assert "fx-pho-dakao" in match_ids(conn, "pho")
    version_before = db.get_meta(conn, "dataset_version")

    rows = read_rows()
    next(r for r in rows if r["id"] == "fx-pho-dakao")["name"] = "Bún Bò Huế Đa Kao"
    report = import_csv(conn, write_rows(tmp_path / "edited.csv", rows))

    assert (report.added, report.updated, report.unchanged) == (0, 1, 5)
    assert "fx-pho-dakao" in match_ids(conn, "bun", "bo", "hue")
    assert "fx-pho-dakao" not in match_ids(conn, "pho")
    assert report.dataset_version != version_before


def test_adding_a_poi_makes_it_searchable(conn, tmp_path):
    import_csv(conn, FIXTURE)
    rows = read_rows()
    new_row = dict(rows[0], id="fx-tra-sua", name="Trà Sữa Mới", category="an_uong", tags="trà sữa")
    report = import_csv(conn, write_rows(tmp_path / "added.csv", rows + [new_row]))

    assert (report.added, report.total) == (1, 7)
    assert match_ids(conn, "tra", "sua") == {"fx-tra-sua"}


def test_any_invalid_row_means_nothing_is_written(conn, tmp_path):
    import_csv(conn, FIXTURE)
    version_before = db.get_meta(conn, "dataset_version")
    rows = read_rows()
    good_new = dict(rows[0], id="fx-new-ok", name="Hợp lệ")
    bad_new = dict(rows[0], id="fx-new-bad", lat="abc")
    report = import_csv(conn, write_rows(tmp_path / "bad.csv", rows + [good_new, bad_new]))

    assert any("lat/lon không phải số" in e for e in report.errors)
    assert poi_count(conn) == 6
    assert conn.execute("SELECT 1 FROM pois WHERE id = 'fx-new-ok'").fetchone() is None
    assert db.get_meta(conn, "dataset_version") == version_before


def test_score_columns_are_rejected(conn, tmp_path):
    rows = [dict(r, bm25="-3.2") for r in read_rows()]
    report = import_csv(conn, write_rows(tmp_path / "scores.csv", rows, POI_FIELDS + ("bm25",)))

    assert report.errors == ["cột không thuộc schema: bm25"]
    assert poi_count(conn) == 0


@pytest.mark.parametrize(
    "change, message",
    [
        ({"id": "fx-circle-k"}, "bị trùng trong file"),
        ({"id": "FX Upper"}, "chỉ được gồm a-z"),
        ({"category": "khach_san"}, "không có trong config"),
        ({"lat": "10.8113570"}, "vượt phạm vi"),
        ({"lat": "95"}, "ngoài miền hợp lệ"),
        ({"source_url": ""}, "thiếu source_url"),
        ({"source_url": "javascript:alert(1)"}, "source_url phải là URL"),
        ({"verification_status": "ok"}, "verification_status 'ok'"),
        ({"retrieved_at": "18/09/2026"}, "retrieved_at phải theo dạng ISO"),
        ({"category": "nha_tro", "listing_url": ""}, "nhà trọ cần listing_url"),
    ],
)
def test_validation_errors(conn, tmp_path, change, message):
    rows = read_rows()
    rows[0].update(change)
    report = import_csv(conn, write_rows(tmp_path / "invalid.csv", rows))

    assert any(message in e for e in report.errors), report.errors
    assert poi_count(conn) == 0


def test_uncertain_row_is_skipped_and_removed(conn, tmp_path):
    import_csv(conn, FIXTURE)
    rows = read_rows()
    next(r for r in rows if r["id"] == "fx-circle-k")["verification_status"] = "uncertain"
    report = import_csv(conn, write_rows(tmp_path / "uncertain.csv", rows))

    assert (report.skipped, report.deleted, report.total) == (1, 1, 5)
    assert "fx-circle-k" not in match_ids(conn, "circle")


def test_absent_rows_are_kept_unless_replace(conn, tmp_path):
    import_csv(conn, FIXTURE)
    subset = write_rows(tmp_path / "subset.csv", read_rows()[:2])

    kept = import_csv(conn, subset)
    assert (kept.deleted, kept.total) == (0, 6)

    replaced = import_csv(conn, subset, replace=True)
    assert (replaced.deleted, replaced.total) == (4, 2)
    assert match_ids(conn, "circle") == set()
