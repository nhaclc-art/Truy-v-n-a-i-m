"""Nạp/cập nhật POI từ CSV vào DB và dựng lại chỉ mục, không cần sửa mã.

Ví dụ: python -m scripts.import_pois data/pois.csv
Mặc định không xóa POI vắng mặt trong CSV; dùng --replace để thay toàn bộ corpus.
"""
import argparse
import sys
from pathlib import Path

from scripts import use_utf8_stdio
from src import db
from src.importer import import_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp POI từ CSV vào SQLite và dựng lại chỉ mục FTS5.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--replace", action="store_true", help="xóa POI không có trong file CSV")
    args = parser.parse_args()

    conn = db.connect()
    try:
        report = import_csv(conn, args.csv_path, replace=args.replace)
    finally:
        conn.close()

    if report.errors:
        print(f"Không ghi gì vào DB. {len(report.errors)} lỗi:", file=sys.stderr)
        for message in report.errors:
            print(f"  - {message}", file=sys.stderr)
        return 1
    print(
        f"Thêm {report.added}, sửa {report.updated}, không đổi {report.unchanged}, "
        f"bỏ qua (uncertain) {report.skipped}, xóa {report.deleted}."
    )
    per_category = ", ".join(f"{k}: {v}" for k, v in report.by_category.items())
    print(f"Tổng POI: {report.total} ({per_category}). dataset_version: {report.dataset_version}")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
