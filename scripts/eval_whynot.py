"""Đánh giá chức năng "Vì sao không có?" (why-not).

Nguồn câu hỏi:
1. Suy ra từ nhãn R5 đã duyệt (eval/queries.csv + eval/qrels.csv): POI liên quan nằm ngoài top-k.
2. Câu hỏi soạn tay eval/whynot_questions.csv, có lý do dự kiến để đo độ đúng của chẩn đoán. Chỉ dùng
   khi mọi dòng đã có người duyệt; --allow-draft cho chạy thử với bản nháp (kết quả ghi rõ NHÁP).

Kết quả: eval/whynot_results.csv, eval/whynot_strategies.csv, eval/whynot_summary.md và
eval/whynot_cases.md (các ca dùng cho phiếu khảo sát eval/whynot_survey.csv).

Ký duyệt câu hỏi soạn tay (sau khi đã đọc hết):
    python -m scripts.eval_whynot --reviewer "Họ tên" --confirm-reviewed
"""
import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from scripts import use_utf8_stdio
from src import db
from src.config import CONFIG_DIR, ROOT, load_app_config, load_campus
from src.evaluation import check_qrels, files_hash, load_queries, read_csv, write_csv
from src.whynot import STRATEGIES, STRATEGY_NAMES
from src.whynot_eval import (
    QUESTION_FIELDS,
    check_authored,
    load_authored,
    questions_from_qrels,
    run_question,
    summarize_rows,
    summarize_strategies,
)

EVAL_DIR = ROOT / "eval"
RESULT_FIELDS = (
    "question_id",
    "source",
    "query_id",
    "query",
    "sort",
    "radius_m",
    "category",
    "poi_id",
    "poi_name",
    "expected_reason",
    "reason",
    "reason_match",
    "in_top_k",
    "original_rank",
    "options_considered",
    "answered",
    "answered_fixed_k",
    "best_family",
    "best_changes",
    "best_rank",
    "best_k",
    "best_penalty",
    "best_retained",
    "unverified_dropped",
    "elapsed_ms",
)
STRATEGY_FIELDS = ("question_id", "source", "query_id", "strategy", "in_top_k", "answered", "answered_fixed_k", "min_penalty", "retained", "k_new")
SURVEY_FIELDS = ("nguoi_tra_loi", "case_id", "hieu_ly_do_1_5", "de_xuat_huu_ich_1_5", "ghi_chu")
# Ca đưa vào phiếu khảo sát: mỗi loại lý do một ca, lấy từ câu hỏi soạn tay.
SURVEY_CASES = ("W01", "W04", "W06", "W09", "W13")
REASON_NAMES = {"TEXT": "thiếu từ khóa", "CATEGORY": "khác danh mục", "RADIUS": "ngoài bán kính", "RANK": "xếp hạng thấp"}


def pct(value) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def num(value, digits: int = 3) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}"


def reason_text(code: str) -> str:
    return " + ".join(REASON_NAMES.get(c, c) for c in code.split("+"))


def sign(path: Path, reviewer: str) -> int:
    rows = read_csv(path)
    today = date.today().isoformat()
    signed = 0
    for row in rows:
        if not (row.get("reviewed_by") and row.get("reviewed_at")):
            row["reviewed_by"], row["reviewed_at"] = reviewer, today
            signed += 1
    write_csv(path, rows, QUESTION_FIELDS)
    print(f"Đã ký {signed} câu hỏi cho người duyệt '{reviewer}' ngày {today}.")
    return 0


def overview_table(groups: list[tuple[str, dict]]) -> list[str]:
    lines = [
        "| Tập câu hỏi | Số câu | Hợp lệ | Trả lời được | Trả lời được, giữ nguyên k | Penalty nhỏ nhất (TB) | Giữ kết quả cũ (TB) | Chẩn đoán đúng | Median / p95 ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, s in groups:
        accuracy = f"{pct(s['reason_accuracy'])} ({s['reason_labeled']} câu)" if s["reason_labeled"] else "—"
        lines.append(
            f"| {name} | {s['questions']} | {s['valid']} | {pct(s['answered'])} | {pct(s['answered_fixed_k'])} | "
            f"{num(s['best_penalty'])} | {pct(s['best_retained'])} | {accuracy} | {num(s['median_ms'], 1)} / {num(s['p95_ms'], 1)} |"
        )
    return lines


def strategy_table(summary: dict[str, dict]) -> list[str]:
    lines = [
        "| Chiến lược | Trả lời được (cho phép tăng k) | Trả lời được, giữ nguyên k | Penalty nhỏ nhất (TB, câu trả lời được) | Giữ kết quả cũ (TB) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in (*STRATEGIES, "ALL"):
        s = summary.get(name)
        if not s:
            continue
        lines.append(
            f"| {name}: {STRATEGY_NAMES[name]} | {pct(s['answered'])} | {pct(s['answered_fixed_k'])} | "
            f"{num(s['min_penalty'])} | {pct(s['retained'])} |"
        )
    return lines


def survey_lines(path: Path) -> list[str]:
    rows = [r for r in read_csv(path) if r.get("case_id")] if path.exists() else []
    if not rows:
        return ["Chưa có câu trả lời khảo sát trong `eval/whynot_survey.csv`."]
    lines = ["| Ca | Số người | Hiểu lý do (TB, 1–5) | Đề xuất hữu ích (TB, 1–5) |", "| --- | ---: | ---: | ---: |"]
    by_case: dict[str, list[dict]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], []).append(r)

    def avg(items, key):
        values = [float(i[key]) for i in items if i.get(key)]
        return sum(values) / len(values) if values else None

    for case, items in sorted(by_case.items()):
        lines.append(f"| {case} | {len(items)} | {num(avg(items, 'hieu_ly_do_1_5'), 2)} | {num(avg(items, 'de_xuat_huu_ich_1_5'), 2)} |")
    lines.append(
        f"| **Tất cả** | {len({r['nguoi_tra_loi'] for r in rows})} người | {num(avg(rows, 'hieu_ly_do_1_5'), 2)} | "
        f"{num(avg(rows, 'de_xuat_huu_ich_1_5'), 2)} |"
    )
    return lines


def write_summary(path: Path, info: dict, groups: list[tuple[str, dict]], strategies: dict, rows: list[dict], survey: list[str]) -> None:
    valid = [r for r in rows if not r["in_top_k"]]
    all_summary = dict(groups)["Tất cả"]
    lines = [
        "# Kết quả đánh giá why-not",
        "",
        f"- Thời điểm chạy (UTC): {info['run_at']}",
        f"- Dataset: `{info['dataset_version']}`; hash cấu hình: `{info['config_hash']}`; k = {info['k']}; "
        f"λ = {info['lambda']}; tối đa {info['max_changes']} thay đổi (nới khi POI bị nhiều bộ lọc chặn).",
        f"- Nguồn câu hỏi: {info['sources']}",
        "- \"Trả lời được\": có ít nhất một truy vấn sửa đưa POI vào top-k' và đã được chạy lại bằng search() để xác nhận. "
        "\"Giữ nguyên k\": truy vấn sửa đưa POI vào đúng top-k ban đầu.",
        "- Penalty = λ·Δk + (1 − λ)·Δq (He & Lo, ICDE 2012; Chen et al., ICDE 2015). Giữ kết quả cũ = tỷ lệ top-k ban đầu còn trong top-k' của truy vấn sửa.",
        f"- Câu hỏi không hợp lệ (POI thật ra đã nằm trong top-k) được loại khỏi trung bình: {all_summary['invalid_in_top_k']}.",
        f"- Đề xuất bị loại vì chạy lại không khớp: {all_summary['unverified_dropped']} (phải bằng 0).",
    ]
    if info["draft"]:
        lines += ["", "> **NHÁP:** có câu hỏi soạn tay chưa được người duyệt ký; không dùng số liệu này trong báo cáo."]
    lines += ["", "## Tổng quan", "", *overview_table(groups), "", "## So sánh chiến lược sửa (mọi câu hỏi hợp lệ)", "", *strategy_table(strategies)]
    lines += ["", "## Phân bố lý do (câu hỏi hợp lệ)", "", "| Lý do | Số câu |", "| --- | ---: |"]
    for code, count in all_summary["reasons"].most_common():
        lines.append(f"| {reason_text(code)} | {count} |")
    authored = [r for r in valid if r["source"] == "authored"]
    if authored:
        lines += ["", "## Câu hỏi soạn tay", "", "| ID | Truy vấn | POI mong đợi | Lý do dự kiến | Lý do hệ thống | Đề xuất tốt nhất | Hạng mới / k' | Penalty |", "| --- | --- | --- | --- | --- | --- | ---: | ---: |"]
        for r in authored:
            mark = "✓" if r["reason_match"] == 1 else "✗"
            lines.append(
                f"| {r['question_id']} | {r['query'] or '(rỗng)'} · {r['radius_m']} m · {r['sort']} | {r['poi_name']} | "
                f"{reason_text(r['expected_reason'])} | {reason_text(r['reason'])} {mark} | {r['best_changes']} | "
                f"{r['best_rank']} / {r['best_k']} | {r['best_penalty']} |"
            )
    lines += [
        "",
        "## Khảo sát người dùng (thăm dò)",
        "",
        *survey,
        "",
        "## Giới hạn",
        "",
        "- Tập câu hỏi nhỏ; nhãn R5 do một người duyệt. Kết quả chỉ mang tính thăm dò, không có ý nghĩa thống kê.",
        "- λ và chi phí từng loại thay đổi đặt tay, chưa tối ưu; penalty chỉ so sánh được giữa các đề xuất cho cùng một câu hỏi.",
        "- Câu hỏi từ nhãn R5 chủ yếu thuộc loại \"xếp hạng thấp\" vì truy xuất hiện không bỏ sót POI liên quan; câu hỏi soạn tay bổ sung các loại còn lại.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_cases(path: Path, cases: list[dict]) -> None:
    lines = [
        "# Các ca why-not dùng cho khảo sát",
        "",
        "Người tham gia đọc từng ca (hoặc xem trình diễn trên ứng dụng) rồi chấm vào `eval/whynot_survey.csv`:",
        "`hieu_ly_do_1_5` (1 = không hiểu vì sao địa điểm vắng mặt, 5 = hiểu rõ) và `de_xuat_huu_ich_1_5`",
        "(1 = đề xuất vô ích, 5 = sẽ dùng ngay). Không ghi thông tin cá nhân ngoài tên/biệt danh người trả lời.",
        "",
    ]
    for case in cases:
        q, res = case["question"], case["result"]
        lines += [
            f"## {q['question_id']}",
            "",
            f"- Truy vấn: “{q['query'] or '(để trống)'}”, bán kính {q['radius_m']} m, danh mục {q['category'] or 'tất cả'}, xếp hạng {q['sort']}.",
            f"- Địa điểm mong đợi: **{res['target']['name']}** ({res['target']['category_label']}).",
            "- Hệ thống giải thích:",
            *[f"  - {r['message']}" for r in res["reasons"]],
            "- Đề xuất sửa truy vấn:",
            *[
                f"  {i}. {' + '.join(c['text'] for c in s['changes'])} → hạng {s['rank']} trong top {s['params']['k']}"
                for i, s in enumerate(res["suggestions"][:3], start=1)
            ],
            "",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Đánh giá chức năng why-not.")
    parser.add_argument("--queries", type=Path, default=EVAL_DIR / "queries.csv")
    parser.add_argument("--qrels", type=Path, default=EVAL_DIR / "qrels.csv")
    parser.add_argument("--questions", type=Path, default=EVAL_DIR / "whynot_questions.csv")
    parser.add_argument("--survey", type=Path, default=EVAL_DIR / "whynot_survey.csv")
    parser.add_argument("--allow-draft", action="store_true", help="dùng cả câu hỏi soạn tay chưa duyệt (kết quả ghi NHÁP)")
    parser.add_argument("--reviewer", help="ký duyệt câu hỏi soạn tay rồi thoát")
    parser.add_argument("--confirm-reviewed", action="store_true", help="xác nhận đã đọc hết câu hỏi soạn tay trước khi ký")
    args = parser.parse_args()

    if args.reviewer is not None:
        if not args.reviewer.strip() or not args.confirm_reviewed:
            print("Cần --reviewer \"Họ tên\" và --confirm-reviewed sau khi đã đọc hết câu hỏi.", file=sys.stderr)
            return 1
        return sign(args.questions, args.reviewer.strip())

    cfg = load_app_config()
    reference_point = load_campus()["reference_point"]
    k = cfg["whynot"]["k"]
    conn = db.connect()
    try:
        queries = load_queries(args.queries)
        qrels = read_csv(args.qrels)
        errors, unreviewed = check_qrels(conn, queries, qrels)
        if errors or unreviewed:
            print("BLOCKED: nhãn R5 chưa đầy đủ hoặc chưa duyệt; chạy python -m scripts.evaluate --check-only để xem.", file=sys.stderr)
            return 2
        questions = questions_from_qrels(conn, cfg, reference_point, queries, qrels, k)
        sources = [f"{len(questions)} câu suy ra từ nhãn R5 ({len(queries)} truy vấn × 3 chế độ)"]

        draft = False
        if args.questions.exists():
            authored_rows = read_csv(args.questions)
            a_errors, a_unreviewed = check_authored(conn, authored_rows)
            if a_errors:
                print(f"BLOCKED: {args.questions.name} có {len(a_errors)} lỗi:", file=sys.stderr)
                for message in a_errors[:20]:
                    print(f"  - {message}", file=sys.stderr)
                return 2
            if a_unreviewed and not args.allow_draft:
                print(
                    f"Bỏ qua {args.questions.name}: {a_unreviewed} câu chưa có người duyệt "
                    "(ký bằng --reviewer ... --confirm-reviewed, hoặc chạy thử bằng --allow-draft).",
                    file=sys.stderr,
                )
            else:
                draft = a_unreviewed > 0
                authored = load_authored(authored_rows)
                questions += authored
                sources.append(f"{len(authored)} câu soạn tay ({args.questions.name}{', NHÁP' if draft else ''})")

        outputs = [run_question(conn, cfg, reference_point, q, k) for q in questions]
        cases = [
            {"question": q, "result": o["result"]}
            for q, o in zip(questions, outputs)
            if q["question_id"] in SURVEY_CASES and not o["result"]["in_top_k"]
        ]
        info = {
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset_version": db.get_meta(conn, "dataset_version"),
            "config_hash": files_hash([CONFIG_DIR / "app.json", CONFIG_DIR / "aliases.json"]),
            "k": k,
            "lambda": cfg["whynot"]["lambda"],
            "max_changes": cfg["whynot"]["max_changes"],
            "sources": "; ".join(sources),
            "draft": draft,
        }
    finally:
        conn.close()

    rows = [o["row"] for o in outputs]
    strategy_rows = [s for o in outputs for s in o["strategies"]]
    groups = [("Tất cả", summarize_rows(rows))]
    from_qrels = [r for r in rows if r["source"] == "qrels"]
    if from_qrels:
        groups.append(("Từ nhãn R5", summarize_rows(from_qrels)))
        groups.append(("Từ nhãn R5, bỏ Q09 (xe buýt)", summarize_rows([r for r in from_qrels if r["query_id"] != "Q09"])))
    authored_rows = [r for r in rows if r["source"] == "authored"]
    if authored_rows:
        groups.append(("Soạn tay", summarize_rows(authored_rows)))

    write_csv(EVAL_DIR / "whynot_results.csv", rows, RESULT_FIELDS)
    write_csv(EVAL_DIR / "whynot_strategies.csv", strategy_rows, STRATEGY_FIELDS)
    if not args.survey.exists():
        write_csv(args.survey, [], SURVEY_FIELDS)
    write_summary(EVAL_DIR / "whynot_summary.md", info, groups, summarize_strategies(strategy_rows), rows, survey_lines(args.survey))
    write_cases(EVAL_DIR / "whynot_cases.md", cases)

    print(f"Dataset {info['dataset_version']}. {info['sources']}.")
    for name, s in groups:
        print(
            f"  {name}: {s['valid']}/{s['questions']} hợp lệ, trả lời được {pct(s['answered'])}, "
            f"giữ nguyên k {pct(s['answered_fixed_k'])}, penalty TB {num(s['best_penalty'])}, "
            f"median {num(s['median_ms'], 1)} ms"
        )
    if draft:
        print("NHÁP: còn câu hỏi soạn tay chưa duyệt.")
    print("Đã ghi eval/whynot_results.csv, whynot_strategies.csv, whynot_summary.md, whynot_cases.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
