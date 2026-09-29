"""Đánh giá chức năng why-not.

Hai nguồn câu hỏi:
- "qrels": suy ra tự động từ nhãn R5 đã duyệt. Với mỗi (truy vấn, chế độ xếp hạng), mỗi POI liên quan
  nằm ngoài top-k là một câu hỏi "vì sao POI này không có?".
- "authored": eval/whynot_questions.csv, người soạn chỉ ra POI mong đợi và lý do dự kiến
  (expected_reason). Lý do dự kiến dùng để đo độ đúng của bước chẩn đoán.

Chỉ số chính: tỷ lệ trả lời được, penalty nhỏ nhất, tỷ lệ giữ kết quả cũ, thời gian xử lý, phân bố lý do,
và so sánh từng chiến lược sửa đơn lẻ (S1–S7) với chiến lược kết hợp theo penalty.
"""
import sqlite3
import statistics
from collections import Counter, defaultdict

from src.evaluation import MODES
from src.search import parse_params, search
from src.whynot import STRATEGIES, in_strategy, why_not

QUESTION_FIELDS = (
    "question_id",
    "query",
    "origin_lat",
    "origin_lon",
    "radius_m",
    "category",
    "sort",
    "poi_id",
    "poi_name",
    "expected_reason",
    "information_need",
    "labeled_by",
    "reviewed_by",
    "reviewed_at",
)
REASON_ORDER = ("TEXT", "CATEGORY", "RADIUS", "RANK")


def search_args(q: dict, sort: str, limit: int) -> dict:
    args = {
        "q": q["query"],
        "lat": str(q["lat"]),
        "lon": str(q["lon"]),
        "origin_mode": "custom",
        "radius_m": str(q["radius_m"]),
        "sort": sort,
        "limit": str(limit),
    }
    if q.get("category"):
        args["category"] = q["category"]
    return args


def questions_from_qrels(conn: sqlite3.Connection, cfg: dict, reference_point: dict, queries: list[dict], qrels: list[dict], k: int) -> list[dict]:
    relevant: dict[str, set[str]] = defaultdict(set)
    for row in qrels:
        if int(row["relevance"]) > 0:
            relevant[row["query_id"]].add(row["poi_id"])
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM pois")}
    questions = []
    for q in queries:
        for mode in MODES:
            params = parse_params(search_args(q, mode, cfg["search"]["max_limit"]), cfg, reference_point)
            top = [i["id"] for i in search(conn, params, cfg)["items"][:k]]
            for poi_id in sorted(relevant[q["query_id"]] - set(top)):
                questions.append(
                    {
                        "question_id": f"{q['query_id']}-{mode}-{poi_id}",
                        "source": "qrels",
                        "query_id": q["query_id"],
                        "query": q["query"],
                        "lat": q["lat"],
                        "lon": q["lon"],
                        "radius_m": q["radius_m"],
                        "category": q["category"],
                        "sort": mode,
                        "poi_id": poi_id,
                        "poi_name": names.get(poi_id, ""),
                        "expected_reason": "",
                    }
                )
    return questions


def load_authored(rows: list[dict]) -> list[dict]:
    return [
        {
            "question_id": r["question_id"],
            "source": "authored",
            "query_id": r["question_id"],
            "query": r["query"],
            "lat": float(r["origin_lat"]),
            "lon": float(r["origin_lon"]),
            "radius_m": int(r["radius_m"]),
            "category": r["category"] or None,
            "sort": r["sort"],
            "poi_id": r["poi_id"],
            "poi_name": r["poi_name"],
            "expected_reason": r["expected_reason"],
            "information_need": r.get("information_need", ""),
        }
        for r in rows
    ]


def check_authored(conn: sqlite3.Connection, rows: list[dict]) -> tuple[list[str], int]:
    """Trả về (lỗi, số dòng chưa duyệt)."""
    ids = {r["id"] for r in conn.execute("SELECT id FROM pois")}
    errors, seen = [], set()
    for line, r in enumerate(rows, start=2):
        if r["question_id"] in seen:
            errors.append(f"dòng {line}: trùng question_id {r['question_id']}")
        seen.add(r["question_id"])
        if r["poi_id"] not in ids:
            errors.append(f"dòng {line}: poi_id {r['poi_id']} không có trong DB")
        reasons = [x for x in r["expected_reason"].split("+") if x]
        if not reasons or any(x not in REASON_ORDER for x in reasons):
            errors.append(f"dòng {line}: expected_reason phải gồm {', '.join(REASON_ORDER)} nối bằng '+'")
    unreviewed = sum(1 for r in rows if not (r.get("reviewed_by") and r.get("reviewed_at")))
    return errors, unreviewed


def run_question(conn: sqlite3.Connection, cfg: dict, reference_point: dict, q: dict, k: int) -> dict:
    params = parse_params(search_args(q, q["sort"], cfg["search"]["max_limit"]), cfg, reference_point)
    result = why_not(conn, params, q["poi_id"], cfg, k, return_all=True)
    options = result["all_options"]
    actual = "+".join(r["code"] for r in result["reasons"])
    best = result["suggestions"][0] if result["suggestions"] else None
    row = {
        "question_id": q["question_id"],
        "source": q["source"],
        "query_id": q["query_id"],
        "query": q["query"],
        "sort": q["sort"],
        "radius_m": q["radius_m"],
        "category": q["category"] or "",
        "poi_id": q["poi_id"],
        "poi_name": q["poi_name"],
        "expected_reason": q["expected_reason"],
        "reason": actual,
        "reason_match": "" if not q["expected_reason"] else int(set(q["expected_reason"].split("+")) == set(actual.split("+"))),
        "in_top_k": int(result["in_top_k"]),
        "original_rank": result["rank"] if result["rank"] is not None else "",
        "options_considered": result["options_considered"],
        "answered": int(best is not None),
        "answered_fixed_k": int(any("k" not in o["dims"] for o in options)),
        "best_family": best["family"] if best else "",
        "best_changes": " + ".join(c["text"] for c in best["changes"]) if best else "",
        "best_rank": best["rank"] if best else "",
        "best_k": best["params"]["k"] if best else "",
        "best_penalty": best["penalty"] if best else "",
        "best_retained": "" if not best or best["retained"] is None else round(best["retained"], 4),
        "unverified_dropped": result["unverified_dropped"],
        "elapsed_ms": result["elapsed_ms"],
    }
    strategies = []
    for name in STRATEGIES:
        members = [o for o in options if in_strategy(o["dims"], name)]
        strategies.append(strategy_row(q, name, members, result["in_top_k"]))
    strategies.append(strategy_row(q, "ALL", options, result["in_top_k"]))
    return {"row": row, "strategies": strategies, "result": result}


def strategy_row(q: dict, name: str, members: list[dict], in_top_k: bool) -> dict:
    best = min(members, key=lambda o: (o["penalty"], -(o["retained"] or 0)), default=None)
    return {
        "question_id": q["question_id"],
        "source": q["source"],
        "query_id": q["query_id"],
        "strategy": name,
        "in_top_k": int(in_top_k),
        "answered": int(best is not None),
        "answered_fixed_k": int(any("k" not in o["dims"] for o in members)),
        "min_penalty": "" if best is None else round(best["penalty"], 4),
        "retained": "" if best is None or best["retained"] is None else round(best["retained"], 4),
        "k_new": "" if best is None else best["k_new"],
    }


def mean(values) -> float | None:
    values = [v for v in values if v != "" and v is not None]
    return sum(values) / len(values) if values else None


def summarize_rows(rows: list[dict]) -> dict:
    valid = [r for r in rows if not r["in_top_k"]]
    times = [r["elapsed_ms"] for r in valid]
    matched = [r["reason_match"] for r in valid if r["reason_match"] != ""]
    return {
        "questions": len(rows),
        "valid": len(valid),
        "invalid_in_top_k": len(rows) - len(valid),
        "answered": mean(r["answered"] for r in valid),
        "answered_fixed_k": mean(r["answered_fixed_k"] for r in valid),
        "best_penalty": mean(r["best_penalty"] for r in valid),
        "best_retained": mean(r["best_retained"] for r in valid),
        "reason_accuracy": mean(matched),
        "reason_labeled": len(matched),
        "median_ms": statistics.median(times) if times else None,
        "p95_ms": sorted(times)[max(0, int(round(0.95 * len(times))) - 1)] if times else None,
        "reasons": Counter(r["reason"] for r in valid),
        "unverified_dropped": sum(r["unverified_dropped"] for r in rows),
    }


def summarize_strategies(strategy_rows: list[dict]) -> dict[str, dict]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for s in strategy_rows:
        if not s["in_top_k"]:
            by_name[s["strategy"]].append(s)
    return {
        name: {
            "questions": len(items),
            "answered": mean(s["answered"] for s in items),
            "answered_fixed_k": mean(s["answered_fixed_k"] for s in items),
            "min_penalty": mean(s["min_penalty"] for s in items),
            "retained": mean(s["retained"] for s in items),
        }
        for name, items in by_name.items()
    }
