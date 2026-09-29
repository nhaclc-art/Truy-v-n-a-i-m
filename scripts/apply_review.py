"""Tạo data/pois.csv = bản nháp data/pois_draft.csv + kết quả duyệt trong data/review_sheet.csv.

Thay cho việc chép tay bản nháp: chạy lại sau mỗi lần build_draft để không mất kết quả duyệt.
Có lỗi trong bảng duyệt thì không ghi file.
"""
import argparse
import csv
import sys
from pathlib import Path

from scripts import use_utf8_stdio
from src.config import ROOT
from src.importer import POI_FIELDS
from src.review import apply_review

DATA_DIR = ROOT / "data"


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Áp bảng duyệt lên bản nháp để tạo data/pois.csv.")
    parser.add_argument("--draft", type=Path, default=DATA_DIR / "pois_draft.csv")
    parser.add_argument("--review", type=Path, default=DATA_DIR / "review_sheet.csv")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "pois.csv")
    args = parser.parse_args()

    reviews = read_rows(args.review) if args.review.exists() else []
    rows, errors, counts, stale = apply_review(read_rows(args.draft), reviews)
    if errors:
        print(f"Không ghi {args.out}. {len(errors)} lỗi trong bảng duyệt:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 1

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POI_FIELDS)
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in POI_FIELDS} for row in rows)

    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "chưa có dòng nào được duyệt"
    print(f"Đã ghi {args.out}: {len(rows)} POI. Kết quả duyệt đã áp: {summary}.")
    if stale:
        print(f"Dòng duyệt không còn trong bản nháp (bỏ qua): {', '.join(stale)}")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
