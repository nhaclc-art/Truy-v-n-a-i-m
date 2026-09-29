"""Đánh giá IR nhỏ (R5): Precision@5, Recall@5 và nDCG@5 cho ba chế độ xếp hạng.

Nhãn (qrels) do người gán/duyệt; module này không sinh nhãn từ điểm xếp hạng. Mỗi truy vấn phải
có nhãn cho toàn bộ POI trong phạm vi (danh mục + bán kính quanh gốc), kể cả POI không khớp văn bản,
nên Recall@5 dùng tổng POI liên quan của cả phạm vi chứ không chỉ các ứng viên truy xuất được.
"""
import csv
import hashlib
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

from src.geo import haversine_m
from src.search import parse_params, search

K = 5
# A: BM25, B: khoảng cách, C: kết hợp (docs/planning/04 §5).
MODES = ("bm25", "distance", "combined")
MODE_NAMES = {"bm25": "A: BM25", "distance": "B: khoảng cách", "combined": "C: kết hợp"}
QREL_FIELDS = (
    "query_id",
    "poi_id",
    "poi_name",
    "category",
    "address",
    "source_url",
    "relevance",
    "reason",
    "labeled_by",
    "reviewed_by",
    "reviewed_at",
)
VALID_RELEVANCE = ("0", "1", "2")


# ---------- Chỉ số ----------

def precision_at_k(ranked: list[str], relevant: set[str], k: int = K) -> float:
    """Vị trí thiếu (trả về ít hơn k kết quả) tính là không liên quan."""
    return sum(1 for poi_id in ranked[:k] if poi_id in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int = K) -> float | None:
    """None khi truy vấn không có POI liên quan (N/A, loại khỏi trung bình)."""
    if not relevant:
        return None
    return sum(1 for poi_id in ranked[:k] if poi_id in relevant) / len(relevant)


def ndcg_at_k(ranked: list[str], gains: dict[str, int], k: int = K) -> float | None:
    """nDCG với gain 2^rel − 1; IDCG tính từ toàn bộ nhãn của truy vấn. None khi IDCG = 0."""
    dcg = sum((2 ** gains.get(poi_id, 0) - 1) / math.log2(i + 2) for i, poi_id in enumerate(ranked[:k]))
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else None


def word_error_rate(reference: list[str], hypothesis: list[str]) -> float | None:
    """WER = (thay + xóa + chèn) / số từ của câu chuẩn, theo khoảng cách Levenshtein trên từ. None khi câu chuẩn rỗng."""
    if not reference:
        return None
    prev = list(range(len(hypothesis) + 1))
    for i, ref_word in enumerate(reference, start=1):
        cur = [i] + [0] * len(hypothesis)
        for j, hyp_word in enumerate(hypothesis, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ref_word != hyp_word))
        prev = cur
    return prev[-1] / len(reference)


def _mean(values) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


# ---------- Dữ liệu đánh giá ----------

def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict], fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_queries(path: Path) -> list[dict]:
    return [
        {
            "query_id": r["query_id"],
            "query": r["query"],
            "lat": float(r["origin_lat"]),
            "lon": float(r["origin_lon"]),
            "radius_m": int(r["radius_m"]),
            "category": r["category"] or None,
            "information_need": r.get("information_need", ""),
        }
        for r in read_csv(path)
    ]


def scope_pois(conn: sqlite3.Connection, query: dict) -> list[sqlite3.Row]:
    """Mọi POI thuộc danh mục của truy vấn (nếu có) và nằm trong bán kính quanh gốc, sắp theo ID."""
    rows = conn.execute("SELECT id, name, category, address, source_url, lat, lon FROM pois ORDER BY id").fetchall()
    return [
        r
        for r in rows
        if (query["category"] is None or r["category"] == query["category"])
        and haversine_m(query["lat"], query["lon"], r["lat"], r["lon"]) <= query["radius_m"]
    ]


def label_rows(conn: sqlite3.Connection, queries: list[dict], existing: list[dict]) -> tuple[list[dict], list[dict]]:
    """Dựng bảng gán nhãn: giữ nhãn đã có, thêm dòng trống cho POI trong phạm vi chưa có nhãn.

    Thứ tự theo query_id rồi poi_id, không theo điểm hay khoảng cách, để người gán nhãn không bị
    dẫn dắt bởi thứ hạng. Trả về (rows, các dòng đã có nhãn nhưng không còn trong phạm vi).
    """
    kept = {(r["query_id"], r["poi_id"]): r for r in existing}
    rows, in_scope = [], set()
    for q in queries:
        for poi in scope_pois(conn, q):
            key = (q["query_id"], poi["id"])
            in_scope.add(key)
            row = dict.fromkeys(QREL_FIELDS, "")
            row.update(kept.get(key, {}))
            row.update(
                query_id=q["query_id"],
                poi_id=poi["id"],
                poi_name=poi["name"],
                category=poi["category"],
                address=poi["address"] or "",
                source_url=poi["source_url"],
            )
            rows.append({k: row[k] for k in QREL_FIELDS})
    rows.sort(key=lambda r: (r["query_id"], r["poi_id"]))
    dropped = [r for key, r in kept.items() if key not in in_scope and r.get("relevance")]
    return rows, dropped


def sign_rows(rows: list[dict], reviewer: str, reviewed_at: str) -> tuple[list[dict], int, list[str]]:
    """Ghi người duyệt cho các dòng chưa có; dòng đã có người duyệt giữ nguyên.

    Từ chối khi còn dòng chưa có relevance hợp lệ: không ký thay cho nhãn chưa gán.
    """
    errors = [
        f"qrels dòng {line}: relevance chưa hợp lệ ('{row.get('relevance', '')}')"
        for line, row in enumerate(rows, start=2)
        if row.get("relevance") not in VALID_RELEVANCE
    ]
    if errors:
        return rows, 0, errors
    signed_rows, signed = [], 0
    for row in rows:
        row = dict(row)
        if not (row.get("reviewed_by") and row.get("reviewed_at")):
            row["reviewed_by"], row["reviewed_at"] = reviewer, reviewed_at
            signed += 1
        signed_rows.append(row)
    return signed_rows, signed, []


def check_qrels(conn: sqlite3.Connection, queries: list[dict], qrels: list[dict]) -> tuple[list[str], int]:
    """Trả về (lỗi chặn đánh giá, số dòng chưa có người duyệt)."""
    errors = []
    query_ids = {q["query_id"] for q in queries}
    labeled: dict[str, set[str]] = defaultdict(set)
    for line, row in enumerate(qrels, start=2):
        qid, pid = row["query_id"], row["poi_id"]
        if qid not in query_ids:
            errors.append(f"qrels dòng {line}: query_id '{qid}' không có trong queries")
            continue
        if pid in labeled[qid]:
            errors.append(f"qrels dòng {line}: trùng cặp ({qid}, {pid})")
            continue
        labeled[qid].add(pid)
        if row.get("relevance") not in VALID_RELEVANCE:
            errors.append(f"qrels dòng {line}: relevance phải là 0, 1 hoặc 2 (đang là '{row.get('relevance', '')}')")
    for q in queries:
        scope = {r["id"] for r in scope_pois(conn, q)}
        missing = sorted(scope - labeled[q["query_id"]])
        extra = sorted(labeled[q["query_id"]] - scope)
        if missing:
            errors.append(f"{q['query_id']}: {len(missing)} POI trong phạm vi chưa có dòng nhãn: {', '.join(missing[:5])}")
        if extra:
            errors.append(f"{q['query_id']}: {len(extra)} nhãn cho POI ngoài phạm vi/không còn trong DB: {', '.join(extra[:5])}")
    unreviewed = sum(1 for row in qrels if not (row.get("reviewed_by") and row.get("reviewed_at")))
    return errors, unreviewed


# ---------- Chạy đánh giá ----------

def evaluate(conn: sqlite3.Connection, cfg: dict, reference_point: dict, queries: list[dict], qrels: list[dict]):
    """Chạy cùng hàm search với API cho từng truy vấn và từng chế độ. Trả về (results, metrics)."""
    gains_by_query: dict[str, dict[str, int]] = defaultdict(dict)
    for row in qrels:
        gains_by_query[row["query_id"]][row["poi_id"]] = int(row["relevance"])

    results, metrics = [], []
    for q in queries:
        gains = gains_by_query[q["query_id"]]
        relevant = {pid for pid, g in gains.items() if g > 0}
        for mode in MODES:
            args = {
                "q": q["query"],
                "lat": str(q["lat"]),
                "lon": str(q["lon"]),
                "origin_mode": "custom",
                "radius_m": str(q["radius_m"]),
                "category": q["category"] or "",
                "sort": mode,
                "limit": str(cfg["search"]["max_limit"]),
            }
            result = search(conn, parse_params(args, cfg, reference_point), cfg)
            ranked = [item["id"] for item in result["items"]]
            for item in result["items"]:
                results.append(
                    {
                        "query_id": q["query_id"],
                        "mode": mode,
                        "rank": item["rank"],
                        "poi_id": item["id"],
                        "poi_name": item["name"],
                        "relevance": gains.get(item["id"], ""),
                        "bm25_raw": item["bm25_raw"],
                        "distance_m": round(item["distance_m"], 1),
                        "score": item["score"],
                    }
                )
            metrics.append(
                {
                    "query_id": q["query_id"],
                    "mode": mode,
                    "sort_effective": result["meta"]["sort_effective"],
                    "returned_count": len(ranked),
                    "relevant_total": len(relevant),
                    "relevant_in_top5": sum(1 for pid in ranked[:K] if pid in relevant),
                    "precision_at_5": precision_at_k(ranked, relevant),
                    "recall_at_5": recall_at_k(ranked, relevant),
                    "ndcg_at_5": ndcg_at_k(ranked, gains),
                    "missed_by_retrieval": ";".join(sorted(relevant - set(ranked))),
                }
            )
    return results, metrics


def summarize(metrics: list[dict]) -> dict[str, dict]:
    summary = {}
    for mode in MODES:
        rows = [m for m in metrics if m["mode"] == mode]
        recalls = [m["recall_at_5"] for m in rows if m["recall_at_5"] is not None]
        ndcgs = [m["ndcg_at_5"] for m in rows if m["ndcg_at_5"] is not None]
        summary[mode] = {
            "queries": len(rows),
            "p5_all": _mean(m["precision_at_5"] for m in rows),
            "p5_answered": _mean(m["precision_at_5"] for m in rows if m["relevant_total"] > 0),
            "r5": _mean(recalls),
            "r5_excluded": len(rows) - len(recalls),
            "ndcg5": _mean(ndcgs),
            "ndcg5_excluded": len(rows) - len(ndcgs),
        }
    return summary


def files_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]
