import csv
from pathlib import Path

import pytest

from src import db
from src.importer import POI_FIELDS, import_csv

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "pois_fixture.csv"


@pytest.fixture
def fixture_db(tmp_path) -> Path:
    """DB tạm đã import 6 POI tổng hợp trong tests/fixtures/pois_fixture.csv."""
    path = tmp_path / "fixture.db"
    conn = db.connect(path)
    try:
        assert import_csv(conn, FIXTURE_CSV).errors == []
    finally:
        conn.close()
    return path


@pytest.fixture
def fixture_rows() -> list[dict]:
    with open(FIXTURE_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def write_csv(tmp_path):
    def write(rows: list[dict], name: str = "custom.csv") -> Path:
        path = tmp_path / name
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=POI_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    return write
