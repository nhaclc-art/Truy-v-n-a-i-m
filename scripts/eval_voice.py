"""Đánh giá tìm bằng giọng nói.

Dữ liệu: eval/voice_queries.csv, mỗi dòng là một lần đọc to một truy vấn R5 (eval/queries.csv) trên ứng
dụng: base_query_id, người nói, thiết bị, câu trình duyệt nghe được (transcript), độ tin cậy. Lấy
transcript từ nút "Tải nhật ký giọng nói" trong ứng dụng.

Hai nhóm chỉ số:
- Nhận dạng: WER (tỷ lệ lỗi từ) của câu nghe được so với truy vấn gốc, tính trên token đã chuẩn hóa
  (bỏ dấu, chữ thường, mở rộng viết tắt), trước và sau bước sửa lỗi gõ (src/spell.py).
- Truy xuất: như scripts.eval_spell (chế độ BM25, tắt/bật sửa lỗi gõ, dùng nhãn R5 của truy vấn gốc):
  tỷ lệ 5 kết quả đầu giống truy vấn gõ đúng, tỷ lệ rỗng, P@5, nDCG@5.

Kết quả: eval/voice_results.csv, eval/voice_summary.md.
"""
import sys
from collections import defaultdict
from datetime import datetime, timezone

from scripts import use_utf8_stdio
from scripts.eval_spell import fmt, mean, run
from src import db
from src.config import ROOT, load_app_config, load_campus
from src.evaluation import K, check_qrels, load_queries, ndcg_at_k, precision_at_k, read_csv, word_error_rate, write_csv
from src.normalize import analyze

EVAL_DIR = ROOT / "eval"
FIELDS = (
    "variant_id",
    "base_query_id",
    "base_query",
    "speaker",
    "device",
    "transcript",
    "confidence",
    "spell",
    "query_used",
    "corrections",
    "wer",
    "returned_count",
    "same_top5_as_base",
    "precision_at_5",
    "ndcg_at_5",
)


def main() -> int:
    cfg = load_app_config()
    ref = load_campus()["reference_point"]
    queries = {q["query_id"]: q for q in load_queries(EVAL_DIR / "queries.csv")}
    qrels = read_csv(EVAL_DIR / "qrels.csv")
    path = EVAL_DIR / "voice_queries.csv"
    variants = [v for v in read_csv(path) if v.get("transcript")] if path.exists() else []
    if not variants:
        print(
            "Chưa có dữ liệu trong eval/voice_queries.csv. Đọc to các truy vấn trong eval/queries.csv bằng nút micro, "
            "bấm \"Tải nhật ký giọng nói\", rồi chép transcript vào file (thêm base_query_id, speaker, device).",
            file=sys.stderr,
        )
        return 1

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
            print(f"BLOCKED: dòng trỏ tới truy vấn không có: {', '.join(unknown)}", file=sys.stderr)
            return 2

        rows = []
        for v in variants:
            base = queries[v["base_query_id"]]
            reference = analyze(base["query"])
            base_top = [i["id"] for i in run(conn, cfg, ref, base, base["query"], True)["items"][:K]]
            g = gains[base["query_id"]]
            relevant = {pid for pid, rel in g.items() if rel > 0}
            for spell in (False, True):
                result = run(conn, cfg, ref, base, v["transcript"], spell)
                ranked = [i["id"] for i in result["items"]]
                used = result["meta"]["query_normalized"].split()
                rows.append(
                    {
                        "variant_id": v["variant_id"],
                        "base_query_id": base["query_id"],
                        "base_query": base["query"],
                        "speaker": v.get("speaker", ""),
                        "device": v.get("device", ""),
                        "transcript": v["transcript"],
                        "confidence": v.get("confidence", ""),
                        "spell": int(spell),
                        "query_used": " ".join(used),
                        "corrections": "; ".join(f"{c['from']} → {c['to']}" for c in result["meta"]["corrections"]),
                        "wer": word_error_rate(reference, used),
                        "returned_count": len(ranked),
                        "same_top5_as_base": int(ranked[:K] == base_top),
                        "precision_at_5": precision_at_k(ranked, relevant),
                        "ndcg_at_5": ndcg_at_k(ranked, g) if relevant else None,
                    }
                )
        version = db.get_meta(conn, "dataset_version")
    finally:
        conn.close()

    write_csv(EVAL_DIR / "voice_results.csv", [{k: ("N/A" if r[k] is None else r[k]) for k in FIELDS} for r in rows], FIELDS)

    def summary(items):
        return {
            "n": len(items),
            "wer": mean(r["wer"] for r in items),
            "exact": mean(int(r["wer"] == 0) for r in items if r["wer"] is not None),
            "same": mean(r["same_top5_as_base"] for r in items),
            "zero": mean(int(r["returned_count"] == 0) for r in items),
            "p5": mean(r["precision_at_5"] for r in items),
            "ndcg": mean(r["ndcg_at_5"] for r in items),
        }

    groups = [("**Tất cả**", rows)]
    for key, label in (("device", "Thiết bị"), ("speaker", "Người nói")):
        for value in sorted({r[key] for r in rows if r[key]}):
            groups.append((f"{label}: {value}", [r for r in rows if r[key] == value]))

    lines = [
        "# Kết quả đánh giá tìm bằng giọng nói",
        "",
        f"- Thời điểm chạy (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Dataset: `{version}`; {len(variants)} lần đọc, {len({v['base_query_id'] for v in variants})} truy vấn gốc, "
        f"{len({v.get('speaker') for v in variants})} người nói. Nhận dạng: Web Speech API của trình duyệt, tiếng Việt (vi-VN).",
        "- WER tính trên token đã chuẩn hóa (bỏ dấu, chữ thường, mở rộng viết tắt). \"Khớp hoàn toàn\": WER = 0. "
        "Truy xuất ở chế độ BM25 với nhãn R5 của truy vấn gốc.",
        "",
        "| Nhóm | Số lần đọc | Sửa lỗi gõ | WER | Khớp hoàn toàn | Giống truy vấn gốc | Rỗng | P@5 | nDCG@5 |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, items in groups:
        for spell in (0, 1):
            s = summary([r for r in items if r["spell"] == spell])
            lines.append(
                f"| {name} | {s['n']} | {'bật' if spell else 'tắt'} | {fmt(s['wer'])} | {fmt(s['exact'], True)} | "
                f"{fmt(s['same'], True)} | {fmt(s['zero'], True)} | {fmt(s['p5'])} | {fmt(s['ndcg'])} |"
            )
    lines += [
        "",
        "## Từng lần đọc (sửa lỗi gõ bật)",
        "",
        "| ID | Truy vấn gốc | Nghe được | Hiểu thành | Chỗ sửa | WER | Giống gốc |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for r in rows:
        if r["spell"]:
            lines.append(
                f"| {r['variant_id']} | {r['base_query']} | {r['transcript']} | {r['query_used'] or '(rỗng)'} | "
                f"{r['corrections'] or '—'} | {fmt(r['wer'])} | {'có' if r['same_top5_as_base'] else 'không'} |"
            )
    lines += [
        "",
        "## Giới hạn",
        "",
        "- Mẫu nhỏ, vài người nói; môi trường ghi (ồn, micro) ảnh hưởng mạnh. Kết quả mang tính thăm dò.",
        "- Chất lượng nhận dạng phụ thuộc dịch vụ của trình duyệt (không thuộc hệ thống này); hệ thống chỉ xử lý câu đã nhận dạng.",
        "- Từ mượn tiếng Anh (photocopy, Circle K, pizza) hay bị nghe thành âm tiết tiếng Việt; bước gộp âm tiết chỉ sửa được khi phần ghép gần một từ có trong dữ liệu.",
        "",
    ]
    (EVAL_DIR / "voice_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for name, items in groups:
        off = summary([r for r in items if r["spell"] == 0])
        on = summary([r for r in items if r["spell"] == 1])
        print(
            f"  {name.strip('*')}: WER {fmt(off['wer'])} → {fmt(on['wer'])}, giống gốc {fmt(off['same'], True)} → "
            f"{fmt(on['same'], True)}, nDCG@5 {fmt(off['ndcg'])} → {fmt(on['ndcg'])}"
        )
    print("Đã ghi eval/voice_results.csv, eval/voice_summary.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
