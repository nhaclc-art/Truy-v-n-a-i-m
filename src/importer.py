"""Nạp CSV POI vào SQLite (R1).

Kiểm tra toàn bộ file trước khi ghi; có lỗi thì không ghi gì. Upsert theo ID ổn định, dựng lại
FTS từ bảng pois và cập nhật dataset_version trong cùng một transaction.
"""
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src import db
from src.config import load_app_config, load_campus
from src.geo import haversine_m, valid_lat_lon
from src.normalize import analyze

POI_FIELDS = (
    "id",
    "name",
    "category",
    "address",
    "lat",
    "lon",
    "description",
    "tags",
    "source_url",
    "source_type",
    "source_id",
    "retrieved_at",
    "verification_status",
    "verified_at",
    "verification_note",
    "listing_url",
    "listing_checked_at",
    "opening_hours",
)
REQUIRED_FIELDS = ("id", "name", "category", "lat", "lon", "source_url", "source_type", "verification_status")
DATE_FIELDS = ("retrieved_at", "verified_at", "listing_checked_at")
STORED_STATUSES = ("source_only", "cross_checked", "field_checked")
# POI 'uncertain' bị loại khỏi corpus: không nạp, và bị xóa nếu đang có trong DB.
EXCLUDED_STATUS = "uncertain"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

_COLUMNS = ", ".join(POI_FIELDS)
_UPSERT_SQL = (
    f"INSERT INTO pois ({_COLUMNS}) VALUES ({', '.join('?' for _ in POI_FIELDS)}) "
    "ON CONFLICT(id) DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in POI_FIELDS[1:])
)


@dataclass
class ImportReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    deleted: int = 0
    total: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    dataset_version: str | None = None
    errors: list[str] = field(default_factory=list)


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _parse_row(raw: dict, line: int, categories: set[str], center: tuple[float, float], scope_m: float):
    """Trả về (row, errors). row là None khi có lỗi."""
    row = {k: (raw.get(k) or "").strip() for k in POI_FIELDS}
    errors = [f"dòng {line}: thiếu {k}" for k in REQUIRED_FIELDS if not row[k]]

    if row["id"] and not ID_PATTERN.match(row["id"]):
        errors.append(f"dòng {line}: id '{row['id']}' chỉ được gồm a-z, 0-9, '-'")
    if row["category"] and row["category"] not in categories:
        errors.append(f"dòng {line}: category '{row['category']}' không có trong config/app.json")
    status = row["verification_status"]
    if status and status not in STORED_STATUSES + (EXCLUDED_STATUS,):
        errors.append(f"dòng {line}: verification_status '{status}' không hợp lệ")
    if row["source_url"] and not _is_http_url(row["source_url"]):
        errors.append(f"dòng {line}: source_url phải là URL http(s)")
    if row["listing_url"] and not _is_http_url(row["listing_url"]):
        errors.append(f"dòng {line}: listing_url phải là URL http(s)")
    if row["category"] == "nha_tro" and not (row["listing_url"] and row["listing_checked_at"]):
        errors.append(f"dòng {line}: nhà trọ cần listing_url và listing_checked_at")
    for name in DATE_FIELDS:
        if row[name]:
            try:
                datetime.fromisoformat(row[name])
            except ValueError:
                errors.append(f"dòng {line}: {name} phải theo dạng ISO, ví dụ 2026-09-18")

    if row["lat"] and row["lon"]:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except ValueError:
            errors.append(f"dòng {line}: lat/lon không phải số")
        else:
            if not valid_lat_lon(lat, lon):
                errors.append(f"dòng {line}: lat/lon ngoài miền hợp lệ")
            else:
                distance = haversine_m(center[0], center[1], lat, lon)
                if distance > scope_m:
                    errors.append(
                        f"dòng {line}: cách cơ sở {distance:.0f} m, vượt phạm vi {scope_m:.0f} m"
                    )
                row["lat"], row["lon"] = lat, lon

    if errors:
        return None, errors
    for name in POI_FIELDS:
        if row[name] == "":
            row[name] = None
    return row, []


def read_csv(path: Path) -> tuple[list[dict], list[str], list[str]]:
    """Trả về (rows cần nạp, id bị loại vì uncertain, errors)."""
    app = load_app_config()
    point = load_campus()["reference_point"]
    categories = {c["id"] for c in app["categories"]}
    center = (point["lat"], point["lon"])
    scope_m = app["dataset_scope_m"]

    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in POI_FIELDS if c not in header]
            unknown = [c for c in header if c not in POI_FIELDS]
            if missing or unknown:
                errors = []
                if missing:
                    errors.append(f"thiếu cột: {', '.join(missing)}")
                if unknown:
                    errors.append(f"cột không thuộc schema: {', '.join(unknown)}")
                return [], [], errors
            raw_rows = [(reader.line_num, raw) for raw in reader]
    except FileNotFoundError:
        return [], [], [f"không tìm thấy file {path}"]
    except UnicodeDecodeError:
        return [], [], ["file phải lưu bằng UTF-8"]

    rows, excluded, errors = [], [], []
    seen: set[str] = set()
    for line, raw in raw_rows:
        poi_id = (raw.get("id") or "").strip()
        if poi_id and poi_id in seen:
            errors.append(f"dòng {line}: id '{poi_id}' bị trùng trong file")
            continue
        seen.add(poi_id)
        if (raw.get("verification_status") or "").strip() == EXCLUDED_STATUS:
            if not ID_PATTERN.match(poi_id):
                errors.append(f"dòng {line}: id '{poi_id}' không hợp lệ")
            else:
                excluded.append(poi_id)
            continue
        row, row_errors = _parse_row(raw, line, categories, center, scope_m)
        errors.extend(row_errors)
        if row:
            rows.append(row)
    return rows, excluded, errors


def rebuild_fts(conn: sqlite3.Connection, category_labels: dict[str, str]) -> None:
    conn.execute("DELETE FROM poi_fts")
    pois = conn.execute("SELECT id, name, category, description, tags FROM pois").fetchall()
    conn.executemany(
        "INSERT INTO poi_fts(poi_id, name, category, description, tags) VALUES (?, ?, ?, ?, ?)",
        [
            (
                p["id"],
                " ".join(analyze(p["name"])),
                " ".join(analyze(category_labels[p["category"]])),
                " ".join(analyze(p["description"])),
                " ".join(analyze(p["tags"])),
            )
            for p in pois
        ],
    )


def compute_dataset_version(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for r in conn.execute(f"SELECT {_COLUMNS} FROM pois ORDER BY id"):
        digest.update(json.dumps([r[c] for c in POI_FIELDS], ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return "ds-" + digest.hexdigest()[:10]


def import_csv(conn: sqlite3.Connection, path: Path, replace: bool = False) -> ImportReport:
    rows, excluded, errors = read_csv(path)
    report = ImportReport(errors=errors, skipped=len(excluded))
    if errors:
        return report

    labels = {c["id"]: c["label"] for c in load_app_config()["categories"]}
    db.init_schema(conn)
    with conn:
        existing = {r["id"]: dict(r) for r in conn.execute(f"SELECT {_COLUMNS} FROM pois")}
        for row in rows:
            old = existing.get(row["id"])
            if old is None:
                report.added += 1
            elif any(old[c] != row[c] for c in POI_FIELDS):
                report.updated += 1
            else:
                report.unchanged += 1
                continue
            conn.execute(_UPSERT_SQL, [row[c] for c in POI_FIELDS])

        to_delete = set(excluded) & existing.keys()
        if replace:
            to_delete |= existing.keys() - {r["id"] for r in rows}
        conn.executemany("DELETE FROM pois WHERE id = ?", [(i,) for i in sorted(to_delete)])
        report.deleted = len(to_delete)

        rebuild_fts(conn, labels)
        report.dataset_version = compute_dataset_version(conn)
        counts = Counter(r["category"] for r in conn.execute("SELECT category FROM pois"))
        report.by_category = dict(sorted(counts.items()))
        report.total = sum(counts.values())
        db.set_meta(conn, "dataset_version", report.dataset_version)
        db.set_meta(conn, "poi_count", str(report.total))
        db.set_meta(conn, "imported_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        db.set_meta(conn, "last_import_file", Path(path).name)
    return report
