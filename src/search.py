"""Truy vấn POI: khớp văn bản (FTS5/BM25) → lọc danh mục → lọc bán kính → xếp hạng.

Ba chế độ xếp hạng dùng cùng một tập ứng viên; điểm kết hợp luôn được tính để đối chiếu.
Query rỗng (sau chuẩn hóa) là duyệt theo vị trí: không chấm BM25, luôn sắp theo khoảng cách.
Các bước retrieve → score_items → rank_items được tách để module why-not dùng lại đúng cùng
công thức và thứ tự sắp xếp với API.
"""
import math
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass

from src import db
from src.geo import haversine_m, valid_lat_lon
from src.normalize import analyze
from src.spell import correct_tokens, vocabulary

ORIGIN_MODES = ("reference", "gps", "simulated", "custom")
MATCH_MODES = ("all", "any")


class SearchError(ValueError):
    """Tham số truy vấn không hợp lệ (API trả 400)."""


@dataclass(frozen=True)
class SearchParams:
    q: str
    lat: float
    lon: float
    origin_mode: str
    radius_m: int
    category: str | None
    sort: str
    limit: int
    # Trọng số văn bản α của chế độ kết hợp (khoảng cách nhận 1 − α); None = theo config/app.json.
    alpha: float | None = None
    # Sửa lỗi gõ cho token không có trong từ vựng (src/spell.py); False = tìm đúng như đã gõ.
    spell: bool = True
    # Cách nối từ: "all" = AND (mặc định, người gõ); "any" = OR (truy vấn dài và nhiễu, ví dụ chữ đọc từ ảnh).
    match: str = "all"


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise SearchError(f"{name} phải là số nguyên") from None


def _parse_coord(value: str, name: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise SearchError(f"{name} phải là số") from None
    if not math.isfinite(number):
        raise SearchError(f"{name} phải là số hữu hạn")
    return number


def parse_origin(args: Mapping[str, str], reference_point: dict) -> tuple[float, float, str]:
    """lat/lon/origin_mode: dùng chung cho tìm kiếm và lập lộ trình (src.itinerary)."""
    lat_raw, lon_raw = args.get("lat"), args.get("lon")
    if not lat_raw and not lon_raw:
        lat, lon = reference_point["lat"], reference_point["lon"]
        default_mode = "reference"
    elif lat_raw and lon_raw:
        lat, lon = _parse_coord(lat_raw, "lat"), _parse_coord(lon_raw, "lon")
        default_mode = "custom"
    else:
        raise SearchError("cần cả lat và lon")
    if not valid_lat_lon(lat, lon):
        raise SearchError("lat/lon ngoài miền hợp lệ")
    origin_mode = args.get("origin_mode") or default_mode
    if origin_mode not in ORIGIN_MODES:
        raise SearchError(f"origin_mode phải thuộc {', '.join(ORIGIN_MODES)}")
    return lat, lon, origin_mode


def parse_params(args: Mapping[str, str], cfg: dict, reference_point: dict) -> SearchParams:
    search_cfg = cfg["search"]

    q = (args.get("q") or "").strip()
    if len(q) > search_cfg["max_query_chars"]:
        raise SearchError(f"query tối đa {search_cfg['max_query_chars']} ký tự")

    lat, lon, origin_mode = parse_origin(args, reference_point)

    radius_raw = args.get("radius_m")
    radius_m = _parse_int(radius_raw, "radius_m") if radius_raw else search_cfg["default_radius_m"]
    if radius_m not in search_cfg["allowed_radii_m"]:
        allowed = ", ".join(str(r) for r in search_cfg["allowed_radii_m"])
        raise SearchError(f"radius_m phải là một trong {allowed}")

    category = args.get("category") or None
    if category is not None and category not in {c["id"] for c in cfg["categories"]}:
        raise SearchError("category không hợp lệ")

    sort = args.get("sort") or search_cfg["default_sort"]
    if sort not in search_cfg["sort_modes"]:
        raise SearchError(f"sort phải thuộc {', '.join(search_cfg['sort_modes'])}")

    limit_raw = args.get("limit")
    limit = _parse_int(limit_raw, "limit") if limit_raw else search_cfg["default_limit"]
    if not 1 <= limit <= search_cfg["max_limit"]:
        raise SearchError(f"limit phải từ 1 đến {search_cfg['max_limit']}")

    alpha_raw = args.get("alpha")
    alpha = None
    if alpha_raw:
        alpha = _parse_coord(alpha_raw, "alpha")
        if not 0 <= alpha <= 1:
            raise SearchError("alpha phải từ 0 đến 1")

    spell_raw = (args.get("spell") or "1").strip().lower()
    if spell_raw not in ("0", "1", "false", "true"):
        raise SearchError("spell phải là 0 hoặc 1")
    spell = spell_raw in ("1", "true")

    match = args.get("match") or "all"
    if match not in MATCH_MODES:
        raise SearchError("match phải là all hoặc any")

    return SearchParams(q, lat, lon, origin_mode, radius_m, category, sort, limit, alpha, spell, match)


def query_tokens(conn: sqlite3.Connection, q: str, spell: bool, cfg: dict) -> tuple[list[str], list[dict]]:
    """Token của truy vấn sau chuẩn hóa và (nếu bật) sửa lỗi gõ; kèm danh sách chỗ đã sửa."""
    tokens = analyze(q)
    if not (tokens and spell and cfg["spell"]["enabled"]):
        return tokens, []
    return correct_tokens(tokens, vocabulary(conn), cfg)


def combined_weights(alpha: float | None, cfg: dict) -> dict:
    """Trọng số chế độ kết hợp: theo config, hoặc {text: α, geo: 1 − α} khi truy vấn chỉ định α."""
    if alpha is None:
        return cfg["ranking"]["combined_weights"]
    return {"text": alpha, "geo": 1 - alpha}


_SORT_KEYS = {
    "distance": lambda item: (item["distance_m"], item["id"]),
    # bm25() của FTS5: càng nhỏ (càng âm) càng khớp.
    "bm25": lambda item: (item["bm25_raw"], item["distance_m"], item["id"]),
    "combined": lambda item: (-item["score"], item["distance_m"], item["id"]),
}


def fts_expression(tokens: list[str], match: str = "all") -> str:
    # Token đã chuẩn hóa chỉ gồm [a-z0-9]; bọc ngoặc kép để FTS5 coi là chữ. Nối bằng khoảng trắng = AND,
    # bằng " OR " = OR (BM25 vẫn ưu tiên tài liệu khớp nhiều từ và từ hiếm).
    if match == "any":
        return " OR ".join(f'"{t}"' for t in dict.fromkeys(tokens))
    return " ".join(f'"{t}"' for t in tokens)


def retrieve(
    conn: sqlite3.Connection,
    tokens: list[str],
    lat: float,
    lon: float,
    radius_m: int,
    category: str | None,
    cfg: dict,
    match: str = "all",
) -> tuple[list[dict], dict]:
    """Truy xuất và lọc: trả về (ứng viên chưa có điểm kết hợp, số lượng sau từng bước)."""
    labels = {c["id"]: c["label"] for c in cfg["categories"]}

    fts_match = None
    if tokens:
        fts_match = fts_expression(tokens, match)
        bm25 = db.bm25_sql(cfg["ranking"]["bm25_column_weights"])
        rows = conn.execute(
            f"SELECT pois.*, {bm25} AS bm25_raw FROM poi_fts "
            "JOIN pois ON pois.id = poi_fts.poi_id WHERE poi_fts MATCH ?",
            (fts_match,),
        ).fetchall()
        text_match_count = len(rows)
    else:
        rows = conn.execute("SELECT pois.*, NULL AS bm25_raw FROM pois").fetchall()
        text_match_count = None

    if category:
        rows = [r for r in rows if r["category"] == category]
    category_match_count = len(rows)

    # Lọc không gian trên toàn bộ ứng viên, trước khi xếp hạng và cắt limit.
    candidates = []
    for r in rows:
        distance = haversine_m(lat, lon, r["lat"], r["lon"])
        if distance <= radius_m:
            candidates.append((r, distance))

    max_s = max((-r["bm25_raw"] for r, _ in candidates), default=0.0) if tokens else 0.0
    items = []
    for r, distance in candidates:
        geo_norm = max(0.0, 1 - distance / radius_m)
        if tokens:
            text_norm = -r["bm25_raw"] / max_s if max_s > 0 else 0.0
        else:
            text_norm = None
        items.append(
            {
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "category_label": labels.get(r["category"], r["category"]),
                "address": r["address"],
                "lat": r["lat"],
                "lon": r["lon"],
                "distance_m": distance,
                "bm25_raw": r["bm25_raw"],
                "text_norm": text_norm,
                "geo_norm": geo_norm,
                "score": None,
                "source_url": r["source_url"],
                "source_type": r["source_type"],
                "verification_status": r["verification_status"],
            }
        )
    stages = {
        "fts_match": fts_match,
        "text_match_count": text_match_count,
        "category_match_count": category_match_count,
        "radius_match_count": len(candidates),
    }
    return items, stages


def score_items(items: list[dict], weights: dict) -> None:
    """Điểm kết hợp = w_text · text_norm + w_geo · geo_norm; bỏ qua khi query rỗng (text_norm None)."""
    for item in items:
        if item["text_norm"] is not None:
            item["score"] = weights["text"] * item["text_norm"] + weights["geo"] * item["geo_norm"]


def rank_items(items: list[dict], sort: str, has_text: bool) -> tuple[list[dict], str]:
    """Sắp toàn bộ ứng viên (chưa cắt limit). Trả về (danh sách đã sắp, chế độ thực dùng)."""
    sort_effective = sort if has_text else "distance"
    return sorted(items, key=_SORT_KEYS[sort_effective]), sort_effective


def search(conn: sqlite3.Connection, params: SearchParams, cfg: dict) -> dict:
    started = time.perf_counter()
    tokens, corrections = query_tokens(conn, params.q, params.spell, cfg)
    items, stages = retrieve(conn, tokens, params.lat, params.lon, params.radius_m, params.category, cfg, params.match)
    weights = combined_weights(params.alpha, cfg)
    score_items(items, weights)
    ranked, sort_effective = rank_items(items, params.sort, bool(tokens))
    returned = ranked[: params.limit]
    for rank, item in enumerate(returned, start=1):
        item["rank"] = rank
    elapsed_ms = (time.perf_counter() - started) * 1000

    return {
        "items": returned,
        "meta": {
            "query": params.q,
            "query_normalized": " ".join(tokens),
            "query_as_typed": " ".join(analyze(params.q)),
            "spell": params.spell,
            "match": params.match,
            "corrections": corrections,
            "fts_match": stages["fts_match"],
            "origin": {"lat": params.lat, "lon": params.lon, "mode": params.origin_mode},
            "radius_m": params.radius_m,
            "category": params.category,
            "sort_requested": params.sort,
            "sort_effective": sort_effective,
            "text_match_count": stages["text_match_count"],
            "category_match_count": stages["category_match_count"],
            "radius_match_count": stages["radius_match_count"],
            "returned_count": len(returned),
            "limit": params.limit,
            "alpha": params.alpha,
            "weights": {"combined": weights, "bm25_columns": cfg["ranking"]["bm25_column_weights"]},
            "elapsed_ms": round(elapsed_ms, 3),
            "dataset_version": db.get_meta(conn, "dataset_version"),
        },
    }
