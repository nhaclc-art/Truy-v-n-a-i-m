"""Tạo/cập nhật bảng gán nhãn eval/qrels.csv từ eval/queries.csv và DB hiện tại.

Giữ nguyên nhãn đã điền, thêm dòng trống cho POI trong phạm vi truy vấn còn thiếu. Chạy lại sau
mỗi lần corpus thay đổi. Dòng sắp theo ID, không theo thứ hạng, để không dẫn dắt người gán nhãn.
"""
import argparse
import sys
from pathlib import Path

from scripts import use_utf8_stdio
from src import db
from src.config import ROOT
from src.evaluation import QREL_FIELDS, label_rows, load_queries, read_csv, write_csv

EVAL_DIR = ROOT / "eval"


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo/cập nhật bảng gán nhãn eval/qrels.csv.")
    parser.add_argument("--queries", type=Path, default=EVAL_DIR / "queries.csv")
    parser.add_argument("--qrels", type=Path, default=EVAL_DIR / "qrels.csv")
    args = parser.parse_args()

    queries = load_queries(args.queries)
    existing = read_csv(args.qrels) if args.qrels.exists() else []
    conn = db.connect()
    try:
        rows, dropped = label_rows(conn, queries, existing)
        version = db.get_meta(conn, "dataset_version")
    finally:
        conn.close()
    write_csv(args.qrels, rows, QREL_FIELDS)

    blank = sum(1 for r in rows if not r["relevance"])
    unreviewed = sum(1 for r in rows if not (r["reviewed_by"] and r["reviewed_at"]))
    print(f"Dataset {version}: {len(queries)} truy vấn, {len(rows)} dòng nhãn → {args.qrels}")
    print(f"Chưa điền relevance: {blank}; chưa có người duyệt: {unreviewed}")
    for row in dropped:
        print(f"Bỏ nhãn vì POI không còn trong phạm vi: {row['query_id']} {row['poi_id']} (relevance={row['relevance']})")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
