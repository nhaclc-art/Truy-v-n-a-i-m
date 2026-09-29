"""Đo thời gian xử lý tìm kiếm trên máy local (microbenchmark của demo, không phải kiểm thử tải).

Gọi /api/search qua Flask test client (cùng tiến trình, không qua mạng) cho các truy vấn trong
eval/queries.csv × 3 chế độ xếp hạng, sau một lượt khởi động không tính. Ghi từng lần đo vào
eval/latency.csv và in median/p95 kèm mô tả máy.
- request_ms: toàn bộ xử lý request trong Flask (kiểm tham số, tìm kiếm, tạo JSON).
- server_ms: riêng phần tìm kiếm (giá trị elapsed_ms trong meta của API).
Không gồm mạng, tải tile bản đồ hay gọi máy chủ chỉ đường.
"""
import argparse
import csv
import math
import os
import platform
import statistics
import sys
import time

from app import create_app
from scripts import use_utf8_stdio
from src.config import ROOT
from src.evaluation import MODES, load_queries

EVAL_DIR = ROOT / "eval"


def percentile(values: list[float], q: float) -> float:
    """Phân vị q (0–1) nội suy tuyến tính."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def main() -> int:
    parser = argparse.ArgumentParser(description="Đo thời gian xử lý tìm kiếm phía server.")
    parser.add_argument("--rounds", type=int, default=3, help="số lượt đo (mỗi lượt = số truy vấn × 3 chế độ)")
    args = parser.parse_args()

    client = create_app().test_client()
    queries = load_queries(EVAL_DIR / "queries.csv")

    def call(query: dict, mode: str):
        return client.get(
            "/api/search",
            query_string={
                "q": query["query"],
                "lat": query["lat"],
                "lon": query["lon"],
                "radius_m": query["radius_m"],
                "category": query["category"] or "",
                "sort": mode,
                "limit": 50,
            },
        )

    for query in queries:  # lượt khởi động: nạp cache SQLite, import module, không tính
        for mode in MODES:
            call(query, mode)

    rows = []
    dataset_version = None
    for round_no in range(1, args.rounds + 1):
        for query in queries:
            for mode in MODES:
                started = time.perf_counter()
                resp = call(query, mode)
                request_ms = (time.perf_counter() - started) * 1000
                if resp.status_code != 200:
                    print(f"Lỗi HTTP {resp.status_code} ở {query['query_id']}/{mode}", file=sys.stderr)
                    return 1
                meta = resp.get_json()["meta"]
                dataset_version = meta["dataset_version"]
                rows.append(
                    {
                        "round": round_no,
                        "query_id": query["query_id"],
                        "mode": mode,
                        "request_ms": round(request_ms, 3),
                        "server_ms": meta["elapsed_ms"],
                        "returned": meta["returned_count"],
                    }
                )

    with open(EVAL_DIR / "latency.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    request_ms = [r["request_ms"] for r in rows]
    server_ms = [r["server_ms"] for r in rows]
    print(f"Máy: {platform.platform()}, {os.cpu_count()} luồng CPU, Python {platform.python_version()}")
    print(f"Dataset {dataset_version}; {len(rows)} lần đo ({len(queries)} truy vấn × {len(MODES)} chế độ × {args.rounds} lượt)")
    print(f"request_ms: median {statistics.median(request_ms):.2f}, p95 {percentile(request_ms, 0.95):.2f}, max {max(request_ms):.2f}")
    print(f"server_ms:  median {statistics.median(server_ms):.2f}, p95 {percentile(server_ms, 0.95):.2f}, max {max(server_ms):.2f}")
    print("Đã ghi eval/latency.csv")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
