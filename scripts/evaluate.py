"""Đánh giá IR (R5): chạy bộ truy vấn trong eval/queries.csv với nhãn eval/qrels.csv.

Chỉ chạy khi mọi POI trong phạm vi từng truy vấn đã có nhãn và mọi dòng nhãn có người duyệt
(reviewed_by, reviewed_at); ngược lại in R5 BLOCKED và không ghi kết quả.
Kết quả: eval/results.csv (xếp hạng), eval/metrics.csv (chỉ số), eval/summary.md (tóm tắt).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts import use_utf8_stdio
from src import db
from src.config import CONFIG_DIR, ROOT, load_app_config, load_campus
from src.evaluation import (
    K,
    MODE_NAMES,
    MODES,
    check_qrels,
    evaluate,
    files_hash,
    load_queries,
    read_csv,
    summarize,
    write_csv,
)

EVAL_DIR = ROOT / "eval"
RESULT_FIELDS = ("query_id", "mode", "rank", "poi_id", "poi_name", "relevance", "bm25_raw", "distance_m", "score")
METRIC_FIELDS = (
    "query_id",
    "mode",
    "sort_effective",
    "returned_count",
    "relevant_total",
    "relevant_in_top5",
    "precision_at_5",
    "recall_at_5",
    "ndcg_at_5",
    "missed_by_retrieval",
)


def fmt(value) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def query_notes(metric: dict) -> str:
    notes = []
    if metric["relevant_total"] == 0:
        notes.append("không có POI liên quan: Recall/nDCG N/A")
    elif metric["relevant_total"] > K:
        notes.append(f"{metric['relevant_total']} POI liên quan > {K}: Recall@{K} tối đa {K}/{metric['relevant_total']}")
    if metric["missed_by_retrieval"]:
        notes.append(f"retrieval bỏ sót: {metric['missed_by_retrieval'].replace(';', ', ')}")
    return "; ".join(notes)


def write_summary(path: Path, info: dict, queries: list[dict], metrics: list[dict], summary: dict) -> None:
    lines = [
        "# Kết quả đánh giá IR",
        "",
        f"- Thời điểm chạy (UTC): {info['run_at']}",
        f"- Dataset: `{info['dataset_version']}`; hash cấu hình tìm kiếm: `{info['config_hash']}`; "
        f"hash queries: `{info['queries_hash']}`; hash qrels: `{info['qrels_hash']}`",
        f"- Người duyệt nhãn: {info['reviewers']}",
        f"- {len(queries)} truy vấn; nhãn gán cho toàn bộ POI trong phạm vi (danh mục + bán kính) của từng truy vấn.",
        f"- Ba chế độ dùng cùng tập ứng viên truy xuất; Recall@{K} chia cho tổng POI liên quan trong nhãn của cả phạm vi.",
        "",
        "## Trung bình theo chế độ",
        "",
        f"| Chế độ | P@{K} (mọi truy vấn) | P@{K} (truy vấn có đáp án) | R@{K} | Loại khỏi R@{K} | nDCG@{K} | Loại khỏi nDCG |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in MODES:
        s = summary[mode]
        lines.append(
            f"| {MODE_NAMES[mode]} | {fmt(s['p5_all'])} | {fmt(s['p5_answered'])} | {fmt(s['r5'])} | "
            f"{s['r5_excluded']} | {fmt(s['ndcg5'])} | {s['ndcg5_excluded']} |"
        )
    lines += [
        "",
        "## Từng truy vấn",
        "",
        f"| Query | Nội dung | Chế độ | Trả về | Liên quan | P@{K} | R@{K} | nDCG@{K} | Ghi chú tự động |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    text = {q["query_id"]: q["query"] for q in queries}
    for m in metrics:
        lines.append(
            f"| {m['query_id']} | {text[m['query_id']]} | {MODE_NAMES[m['mode']]} | {m['returned_count']} | "
            f"{m['relevant_total']} | {fmt(m['precision_at_5'])} | {fmt(m['recall_at_5'])} | "
            f"{fmt(m['ndcg_at_5'])} | {query_notes(m)} |"
        )
    lines += [
        "",
        "## Giới hạn",
        "",
        f"- Đánh giá thăm dò trên corpus nhỏ và {len(queries)} truy vấn; không có ý nghĩa thống kê, không kết luận chế độ nào vượt trội chung.",
        "- Nhãn nhị phân theo nhu cầu của từng truy vấn; nDCG không phản ánh mức hữu ích hay khoảng cách chi tiết.",
        "- Trọng số chế độ kết hợp đặt tay, không chỉnh theo bộ truy vấn này.",
        "- Nhận xét từng truy vấn của người đánh giá: bổ sung bên dưới.",
        "",
        "## Nhận xét của người đánh giá",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy đánh giá IR cho ba chế độ xếp hạng.")
    parser.add_argument("--queries", type=Path, default=EVAL_DIR / "queries.csv")
    parser.add_argument("--qrels", type=Path, default=EVAL_DIR / "qrels.csv")
    parser.add_argument("--check-only", action="store_true", help="chỉ kiểm tra độ phủ và trạng thái duyệt nhãn")
    args = parser.parse_args()

    cfg = load_app_config()
    reference_point = load_campus()["reference_point"]
    queries = load_queries(args.queries)
    qrels = read_csv(args.qrels) if args.qrels.exists() else []

    conn = db.connect()
    try:
        errors, unreviewed = check_qrels(conn, queries, qrels)
        if errors:
            print(f"R5 BLOCKED: nhãn chưa đầy đủ/hợp lệ ({len(errors)} lỗi).", file=sys.stderr)
            for message in errors[:30]:
                print(f"  - {message}", file=sys.stderr)
            return 2
        if unreviewed:
            print(f"R5 BLOCKED: {unreviewed} dòng nhãn chưa có reviewed_by/reviewed_at; không ghi kết quả.", file=sys.stderr)
            return 2
        if args.check_only:
            print(f"Nhãn đầy đủ và đã duyệt cho {len(queries)} truy vấn ({len(qrels)} dòng).")
            return 0

        results, metrics = evaluate(conn, cfg, reference_point, queries, qrels)
        info = {
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset_version": db.get_meta(conn, "dataset_version"),
            "config_hash": files_hash([CONFIG_DIR / "app.json", CONFIG_DIR / "aliases.json"]),
            "queries_hash": files_hash([args.queries]),
            "qrels_hash": files_hash([args.qrels]),
            "reviewers": ", ".join(sorted({r["reviewed_by"] for r in qrels})),
        }
    finally:
        conn.close()

    summary = summarize(metrics)
    write_csv(EVAL_DIR / "results.csv", results, RESULT_FIELDS)
    write_csv(
        EVAL_DIR / "metrics.csv",
        [{k: ("N/A" if m[k] is None else m[k]) for k in METRIC_FIELDS} for m in metrics],
        METRIC_FIELDS,
    )
    write_summary(EVAL_DIR / "summary.md", info, queries, metrics, summary)

    print(f"Dataset {info['dataset_version']}, {len(queries)} truy vấn. Trung bình:")
    for mode in MODES:
        s = summary[mode]
        print(
            f"  {MODE_NAMES[mode]}: P@{K} {fmt(s['p5_all'])}, R@{K} {fmt(s['r5'])} "
            f"(loại {s['r5_excluded']}), nDCG@{K} {fmt(s['ndcg5'])}"
        )
    print("Đã ghi eval/results.csv, eval/metrics.csv, eval/summary.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
