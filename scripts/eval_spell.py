"""Đánh giá độ bền với lỗi gõ (phương án B).

Mỗi dòng eval/typo_queries.csv là một biến thể gõ sai của một truy vấn R5 (eval/queries.csv):
sai chữ, sót chữ Telex, gõ dính, sai dấu. Biến thể dùng lại vị trí, bán kính, danh mục và nhãn
(eval/qrels.csv) của truy vấn gốc, nên đo được chất lượng mà không cần gán nhãn mới.
Mỗi biến thể chạy hai lần ở chế độ BM25 (tách riêng tác động lên khớp văn bản): tắt và bật sửa lỗi gõ.

Kết quả: eval/spell_results.csv, eval/spell_summary.md.
"""
import sys
from collections import defaultdict
from datetime import datetime, timezone

from scripts import use_utf8_stdio
from src import db
from src.config import CONFIG_DIR, ROOT, load_app_config, load_campus
from src.evaluation import K, check_qrels, files_hash, load_queries, ndcg_at_k, precision_at_k, read_csv, write_csv
from src.search import parse_params, search

EVAL_DIR = ROOT / "eval"
MODE = "bm25"
TYPE_NAMES = {"sai_chu": "Sai chữ / đảo chữ", "telex": "Sót chữ Telex", "go_dinh": "Gõ dính", "sai_dau": "Sai dấu"}
FIELDS = (
    "variant_id",
    "base_query_id",
    "base_query",
    "query",
    "variant_type",
    "spell",
    "query_used",
    "corrections",
    "returned_count",
    "same_top5_as_base",
    "precision_at_5",
    "ndcg_at_5",
)


def run(conn, cfg, ref, base: dict, text: str, spell: bool):
    args = {
        "q": text,
        "lat": str(base["lat"]),
        "lon": str(base["lon"]),
        "origin_mode": "custom",
        "radius_m": str(base["radius_m"]),
        "sort": MODE,
        "limit": str(cfg["search"]["max_limit"]),
        "spell": "1" if spell else "0",
    }
    if base["category"]:
        args["category"] = base["category"]
    return search(conn, parse_params(args, cfg, ref), cfg)


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def fmt(value, pct: bool = False) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%" if pct else f"{value:.4f}"


def main() -> int:
    cfg = load_app_config()
    ref = load_campus()["reference_point"]
    queries = {q["query_id"]: q for q in load_queries(EVAL_DIR / "queries.csv")}
    qrels = read_csv(EVAL_DIR / "qrels.csv")
    variants = read_csv(EVAL_DIR / "typo_queries.csv")

    gains: dict[str, dict[str, int]] = defaultdict(dict)
    for row in qrels:
        gains[row["query_id"]][row["poi_id"]] = int(row["relevance"])

    conn = db.connect()
    try:
        errors, unreviewed = check_qrels(conn, list(queries.values()), qrels)
        if errors or unreviewed:
            print("BLOCKED: nhãn R5 chưa đầy đủ hoặc chưa duyệt; chạy python -m scripts.evaluate --check-only.", file=sys.stderr)
            return 2
        unknown = [v["variant_id"] for v in variants if v["base_query_id"] not in queries]
        if unknown:
            print(f"BLOCKED: biến thể trỏ tới truy vấn không có: {', '.join(unknown)}", file=sys.stderr)
            return 2

        rows = []
        for v in variants:
            base = queries[v["base_query_id"]]
            base_top = [i["id"] for i in run(conn, cfg, ref, base, base["query"], True)["items"][:K]]
            g = gains[base["query_id"]]
            relevant = {pid for pid, rel in g.items() if rel > 0}
            for spell in (False, True):
                result = run(conn, cfg, ref, base, v["query"], spell)
                ranked = [i["id"] for i in result["items"]]
                rows.append(
                    {
                        "variant_id": v["variant_id"],
                        "base_query_id": base["query_id"],
                        "base_query": base["query"],
                        "query": v["query"],
                        "variant_type": v["variant_type"],
                        "spell": int(spell),
                        "query_used": result["meta"]["query_normalized"],
                        "corrections": "; ".join(f"{c['from']} → {c['to']}" for c in result["meta"]["corrections"]),
                        "returned_count": len(ranked),
                        "same_top5_as_base": int(ranked[:K] == base_top),
                        "precision_at_5": precision_at_k(ranked, relevant),
                        "ndcg_at_5": ndcg_at_k(ranked, g) if relevant else None,
                    }
                )
        version = db.get_meta(conn, "dataset_version")
    finally:
        conn.close()

    write_csv(EVAL_DIR / "spell_results.csv", [{k: ("N/A" if r[k] is None else r[k]) for k in FIELDS} for r in rows], FIELDS)

    def summary(items):
        return {
            "n": len(items),
            "same": mean(r["same_top5_as_base"] for r in items),
            "zero": mean(int(r["returned_count"] == 0) for r in items),
            "p5": mean(r["precision_at_5"] for r in items),
            "ndcg": mean(r["ndcg_at_5"] for r in items),
        }

    lines = [
        "# Kết quả đánh giá sửa lỗi gõ",
        "",
        f"- Thời điểm chạy (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Dataset: `{version}`; hash cấu hình: `{files_hash([CONFIG_DIR / 'app.json', CONFIG_DIR / 'aliases.json'])}`; "
        f"hash biến thể: `{files_hash([EVAL_DIR / 'typo_queries.csv'])}`",
        f"- {len(variants)} biến thể gõ sai của các truy vấn R5; dùng nhãn `eval/qrels.csv` của truy vấn gốc; chế độ xếp hạng BM25.",
        "- \"Giống truy vấn gốc\": 5 kết quả đầu trùng khớp (cùng thứ tự) với truy vấn gõ đúng. \"Rỗng\": không trả về kết quả nào.",
        "",
        "## Theo loại lỗi",
        "",
        "| Loại lỗi | Số biến thể | Sửa lỗi gõ | Giống truy vấn gốc | Rỗng | P@5 | nDCG@5 |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    groups = [(TYPE_NAMES.get(t, t), [r for r in rows if r["variant_type"] == t]) for t in TYPE_NAMES]
    groups.append(("**Tất cả**", rows))
    for name, items in groups:
        for spell in (0, 1):
            s = summary([r for r in items if r["spell"] == spell])
            if not s["n"]:
                continue
            lines.append(
                f"| {name} | {s['n']} | {'bật' if spell else 'tắt'} | {fmt(s['same'], True)} | {fmt(s['zero'], True)} | "
                f"{fmt(s['p5'])} | {fmt(s['ndcg'])} |"
            )
    lines += [
        "",
        "## Từng biến thể (sửa lỗi gõ bật)",
        "",
        "| ID | Gốc | Gõ | Đã hiểu thành | Chỗ sửa | Giống gốc | nDCG@5 |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for r in rows:
        if r["spell"]:
            lines.append(
                f"| {r['variant_id']} | {r['base_query']} | {r['query']} | {r['query_used'] or '(rỗng)'} | {r['corrections'] or '—'} | "
                f"{'có' if r['same_top5_as_base'] else 'không'} | {fmt(r['ndcg_at_5'])} |"
            )
    lines += [
        "",
        "## Giới hạn",
        "",
        "- Biến thể do Claude soạn để phủ các kiểu lỗi thường gặp, không lấy từ nhật ký truy vấn thật; tỷ lệ lỗi thật chưa biết.",
        "- Từ dưới 4 ký tự và từ là âm tiết tiếng Việt hợp lệ không được sửa (tránh đổi nghĩa), nên các lỗi như \"caf\" vẫn thất bại.",
        "- Từ điển sửa lỗi là từ vựng của chính corpus nhỏ; từ đúng nhưng không có trong dữ liệu không được \"sửa\" thành từ khác.",
        "",
    ]
    (EVAL_DIR / "spell_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for name, items in groups:
        off = summary([r for r in items if r["spell"] == 0])
        on = summary([r for r in items if r["spell"] == 1])
        print(f"  {name.strip('*')}: giống gốc {fmt(off['same'], True)} → {fmt(on['same'], True)}, nDCG@5 {fmt(off['ndcg'])} → {fmt(on['ndcg'])}")
    print("Đã ghi eval/spell_results.csv, eval/spell_summary.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
