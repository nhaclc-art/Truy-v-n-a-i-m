"""Đánh giá tìm bằng ảnh biển hiệu (OCR).

Dữ liệu: eval/ocr_cases.csv, mỗi dòng một ảnh biển hiệu đã chụp và đọc trên ứng dụng:
- case_id; target_poi_id: địa điểm đúng trong data/pois.csv, để trống nếu quán KHÔNG có trong dữ liệu
  (ca âm, dùng đo tỷ lệ "nhận nhầm");
- device, ocr_text (chép nguyên văn từ "Tải nhật ký ảnh", không sửa tay), ocr_confidence, note.

So sánh ba cách dựng truy vấn từ cùng một đoạn chữ (xếp BM25, gốc là tâm khuôn viên, bán kính 2 km,
không lọc danh mục):
- A. Gõ nguyên văn (AND): như người dùng dán cả đoạn chữ vào ô tìm kiếm.
- B. OR, không lọc: mọi token nối OR.
- C. Hệ thống: src/ocr_query.py (sửa nhầm ký tự OCR, sửa lỗi gõ, bỏ số/từ lạ/từ quá phổ biến, giữ từ hiếm) rồi nối OR.
Chỉ số với ca dương: Hit@1, Hit@3, MRR (hạng của địa điểm đúng). Với ca âm: tỷ lệ vẫn trả về kết quả.
Thêm: tỷ lệ token trong tên địa điểm đúng có mặt trong chữ đọc được (đo chất lượng OCR, tách khỏi truy xuất).

Kết quả: eval/ocr_results.csv, eval/ocr_summary.md.
"""
import sys
from datetime import datetime, timezone

from scripts import use_utf8_stdio
from scripts.eval_spell import fmt, mean
from src import db
from src.config import ROOT, load_app_config, load_campus
from src.evaluation import read_csv, write_csv
from src.normalize import analyze
from src.ocr_query import build_ocr_query
from src.search import rank_items, retrieve, score_items

EVAL_DIR = ROOT / "eval"
CONFIGS = {
    "A": "Gõ nguyên văn (AND)",
    "B": "OR, không lọc",
    "C": "Hệ thống: sửa + lọc + OR",
}
FIELDS = ("case_id", "target_poi_id", "target_name", "device", "config", "query_tokens", "returned_count", "target_rank", "top1_id", "top1_name", "name_token_recall")


def ranked_ids(conn, cfg, ref, tokens: list[str], match: str) -> list[dict]:
    if not tokens:
        return []
    items, _ = retrieve(conn, tokens, ref["lat"], ref["lon"], cfg["ocr"]["search_radius_m"], None, cfg, match)
    score_items(items, cfg["ranking"]["combined_weights"])
    ranked, _ = rank_items(items, "bm25", True)
    return ranked


def main() -> int:
    cfg = load_app_config()
    ref = load_campus()["reference_point"]
    path = EVAL_DIR / "ocr_cases.csv"
    cases = [c for c in read_csv(path) if c.get("ocr_text")] if path.exists() else []
    if not cases:
        print(
            "Chưa có dữ liệu trong eval/ocr_cases.csv. Chụp biển hiệu bằng nút máy ảnh, bấm \"Tải nhật ký ảnh\", "
            "chép ocr_text vào file và điền target_poi_id (để trống nếu quán không có trong dữ liệu).",
            file=sys.stderr,
        )
        return 1

    conn = db.connect()
    try:
        names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM pois")}
        unknown = [c["case_id"] for c in cases if c["target_poi_id"] and c["target_poi_id"] not in names]
        if unknown:
            print(f"BLOCKED: target_poi_id không có trong DB ở ca {', '.join(unknown)}", file=sys.stderr)
            return 2
        rows = []
        for c in cases:
            raw = analyze(c["ocr_text"])
            built = build_ocr_query(conn, c["ocr_text"], cfg)
            token_sets = {"A": (raw, "all"), "B": (raw, "any"), "C": (built["query"].split(), "any")}
            target = c["target_poi_id"]
            name_tokens = set(analyze(names.get(target, ""))) if target else set()
            recall = len(name_tokens & set(raw)) / len(name_tokens) if name_tokens else None
            for key, (tokens, match) in token_sets.items():
                ranked = ranked_ids(conn, cfg, ref, tokens, match)
                ids = [i["id"] for i in ranked]
                rows.append(
                    {
                        "case_id": c["case_id"],
                        "target_poi_id": target,
                        "target_name": names.get(target, ""),
                        "device": c.get("device", ""),
                        "config": key,
                        "query_tokens": " ".join(tokens) if key == "C" else f"{len(tokens)} token",
                        "returned_count": len(ids),
                        "target_rank": ids.index(target) + 1 if target in ids else None,
                        "top1_id": ids[0] if ids else "",
                        "top1_name": ranked[0]["name"] if ranked else "",
                        "name_token_recall": recall,
                    }
                )
        version = db.get_meta(conn, "dataset_version")
    finally:
        conn.close()

    write_csv(EVAL_DIR / "ocr_results.csv", [{k: ("" if r[k] is None else r[k]) for k in FIELDS} for r in rows], FIELDS)

    positives = [r for r in rows if r["target_poi_id"]]
    negatives = [r for r in rows if not r["target_poi_id"]]
    lines = [
        "# Kết quả đánh giá tìm bằng ảnh biển hiệu",
        "",
        f"- Thời điểm chạy (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Dataset: `{version}`; {len(cases)} ảnh ({len({r['case_id'] for r in positives})} quán có trong dữ liệu, "
        f"{len({r['case_id'] for r in negatives})} quán không có). OCR: Tesseract.js 5.1.1 (vie + eng, best_int) trong trình duyệt.",
        "- Xếp BM25, gốc tâm khuôn viên, bán kính 2 km, không lọc danh mục. Chữ OCR chép nguyên văn từ nhật ký ứng dụng.",
        f"- Tỷ lệ token của tên quán có trong chữ đọc được (chất lượng OCR): {fmt(mean(r['name_token_recall'] for r in positives if r['config'] == 'C'), True)}.",
        "",
        "| Cách dựng truy vấn | Hit@1 | Hit@3 | MRR | Rỗng (ca dương) | Vẫn trả kết quả (ca âm) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, name in CONFIGS.items():
        pos = [r for r in positives if r["config"] == key]
        neg = [r for r in negatives if r["config"] == key]
        lines.append(
            f"| {key}. {name} | {fmt(mean(int(r['target_rank'] == 1) for r in pos), True)} | "
            f"{fmt(mean(int(r['target_rank'] is not None and r['target_rank'] <= 3) for r in pos), True)} | "
            f"{fmt(mean((1 / r['target_rank']) if r['target_rank'] else 0 for r in pos))} | "
            f"{fmt(mean(int(r['returned_count'] == 0) for r in pos), True)} | {fmt(mean(int(r['returned_count'] > 0) for r in neg), True)} |"
        )
    lines += [
        "",
        "## Từng ảnh (cách C)",
        "",
        "| Ca | Quán đúng | Truy vấn dựng được | Hạng quán đúng | Kết quả đầu |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for r in rows:
        if r["config"] == "C":
            lines.append(
                f"| {r['case_id']} | {r['target_name'] or '(không có trong dữ liệu)'} | {r['query_tokens'] or '(rỗng)'} | "
                f"{r['target_rank'] or '—'} | {r['top1_name'] or '—'} |"
            )
    lines += [
        "",
        "## Giới hạn",
        "",
        "- Ít ảnh, do một người chụp quanh cơ sở; góc chụp, ánh sáng, font biển hiệu ảnh hưởng mạnh tới OCR.",
        "- Ca âm (quán không có trong dữ liệu) cho thấy tìm kiểu OR gần như luôn trả về một địa điểm nào đó; giao diện ghi rõ \"Có thể là\" và cho xem chữ đọc được để người dùng tự kiểm.",
        "",
    ]
    (EVAL_DIR / "ocr_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[6:6 + 2 + len(CONFIGS)]))
    print("Đã ghi eval/ocr_results.csv, eval/ocr_summary.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
