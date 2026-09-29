"""Lập lộ trình nhiều chặng (ví dụ: cà phê → ăn tối → xem phim) trong một giới hạn quãng đường.

Đây là bài toán tối ưu không gian theo chuỗi (chọn một địa điểm cho mỗi chặng, tối thiểu quãng
đường di chuyển và tối đa độ khớp từ khóa), khác với truy vấn top-k của src.search: một người dùng,
một chuỗi điểm dừng cố định thứ tự, không phải nhiều người cùng tìm điểm gặp (group nearest neighbor).

Phần IR nằm ở từng chặng: mỗi chặng là một truy vấn từ khóa, lấy ứng viên bằng đúng
src.search.retrieve (chỉ mục đảo FTS5 + BM25 + sửa lỗi gõ), rồi mới vét cạn tổ hợp giữa các chặng.
Corpus nhỏ (~100 địa điểm) và mỗi chặng bị cắt về top max_candidates_per_leg ứng viên khớp tốt nhất,
nên vét cạn vẫn nhanh; không cần thuật toán tối ưu tổ hợp (TSP, quy hoạch động) cho quy mô này.

Quãng đường giữa các điểm dùng Haversine (đường chim bay) nhân "hệ số quanh co" đặt tay (đường phố
không đi thẳng); đây chỉ là ước tính để lọc và xếp hạng nhanh, KHÔNG phải quãng đường đi bộ thật.
Khi người dùng chọn một lộ trình, giao diện gọi /api/route (OSRM) cho từng chặng để lấy quãng đường
thật — tái dùng đúng endpoint chỉ đường đã có, không thêm lệnh gọi máy chủ ngoài nào.

Không xử lý giờ chiếu phim, giờ mở cửa hay tình trạng còn phòng/còn chỗ: "ngân sách thời gian" chỉ là
thời gian đi bộ ước tính cộng thời gian ở mỗi chặng do người dùng tự nhập (giả định, không tra được
từ dữ liệu hiện có).
"""
import itertools
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass

from src.geo import haversine_m
from src.search import SearchError, parse_origin, query_tokens, retrieve


class ItineraryError(ValueError):
    """Tham số lộ trình không hợp lệ (API trả 400)."""


@dataclass(frozen=True)
class ItineraryParams:
    legs: tuple[str, ...]
    lat: float
    lon: float
    origin_mode: str
    max_distance_m: int
    dwell_min: tuple[int, ...]
    limit: int


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise ItineraryError(f"{name} phải là số nguyên") from None
    if parsed <= 0:
        raise ItineraryError(f"{name} phải > 0")
    return parsed


def parse_itinerary_params(args: Mapping[str, str], cfg: dict, reference_point: dict) -> ItineraryParams:
    icfg = cfg["itinerary"]
    legs = tuple(s.strip() for s in args.getlist("stop") if s.strip())
    if not icfg["min_legs"] <= len(legs) <= icfg["max_legs"]:
        raise ItineraryError(f"cần {icfg['min_legs']}–{icfg['max_legs']} chặng (tham số stop=…), đang có {len(legs)}")
    too_long = [s for s in legs if len(s) > cfg["search"]["max_query_chars"]]
    if too_long:
        raise ItineraryError(f"mỗi chặng tối đa {cfg['search']['max_query_chars']} ký tự")

    # parse_origin (dùng chung với src.search, đã tự kiểm lat/lon hợp lệ) ném SearchError; module này
    # chỉ để lộ ItineraryError ra ngoài (app.py chỉ bắt ItineraryError cho endpoint /api/itinerary).
    try:
        lat, lon, origin_mode = parse_origin(args, reference_point)
    except SearchError as exc:
        raise ItineraryError(str(exc)) from exc

    max_distance_raw = args.get("max_distance_m")
    max_distance_m = _parse_positive_int(max_distance_raw, "max_distance_m") if max_distance_raw else icfg["default_max_distance_m"]

    dwell_raw = args.getlist("dwell_min")
    if dwell_raw:
        if len(dwell_raw) not in (1, len(legs)):
            raise ItineraryError(f"cần 1 giá trị dwell_min (áp cho mọi chặng) hoặc đúng {len(legs)} giá trị")
        try:
            parsed = [int(x) for x in dwell_raw]
        except ValueError:
            raise ItineraryError("dwell_min phải là số nguyên") from None
        if any(d < 0 for d in parsed):
            raise ItineraryError("dwell_min phải ≥ 0")
        dwell_min = tuple(parsed * len(legs)) if len(parsed) == 1 else tuple(parsed)
    else:
        dwell_min = tuple(icfg["default_dwell_min"] for _ in legs)

    limit_raw = args.get("limit")
    limit = _parse_positive_int(limit_raw, "limit") if limit_raw else icfg["max_results"]
    if limit > 10:
        raise ItineraryError("limit tối đa 10")

    return ItineraryParams(legs, lat, lon, origin_mode, max_distance_m, dwell_min, limit)


def leg_pool(conn: sqlite3.Connection, cfg: dict, leg_text: str, lat: float, lon: float) -> dict:
    """Ứng viên khớp từ khóa của một chặng: sửa lỗi gõ, khớp BM25 trên toàn corpus quanh (lat, lon),
    giữ lại top max_candidates_per_leg (khớp tốt nhất trước, gần hơn thì đứng trước khi hòa)."""
    icfg = cfg["itinerary"]
    tokens, corrections = query_tokens(conn, leg_text, True, cfg)
    if not tokens:
        return {"tokens": tokens, "corrections": corrections, "match_count": 0, "candidates": []}
    items, _ = retrieve(conn, tokens, lat, lon, icfg["search_radius_m"], None, cfg)
    items.sort(key=lambda it: (-it["text_norm"], it["distance_m"], it["id"]))
    return {
        "tokens": tokens,
        "corrections": corrections,
        "match_count": len(items),
        "candidates": items[: icfg["max_candidates_per_leg"]],
    }


def _stop_view(leg_index: int, leg_query: str, candidate: dict, distance_from_prev_m: float, dwell_min: int) -> dict:
    return {
        "leg": leg_index,
        "query": leg_query,
        "id": candidate["id"],
        "name": candidate["name"],
        "category": candidate["category"],
        "category_label": candidate["category_label"],
        "address": candidate["address"],
        "lat": candidate["lat"],
        "lon": candidate["lon"],
        "text_norm": candidate["text_norm"],
        "distance_from_prev_m": distance_from_prev_m,
        "dwell_min": dwell_min,
    }


def plan(conn: sqlite3.Connection, cfg: dict, params: ItineraryParams) -> dict:
    started = time.perf_counter()
    icfg = cfg["itinerary"]
    weights = icfg["weights"]
    detour = icfg["detour_factor"]

    pools = [leg_pool(conn, cfg, leg, params.lat, params.lon) for leg in params.legs]
    origin_point = (params.lat, params.lon)

    combos_considered = 0
    combos_within_distance = 0
    min_total_distance_m = None
    routes: list[dict] = []
    if all(pool["candidates"] for pool in pools):
        for combo in itertools.product(*(pool["candidates"] for pool in pools)):
            ids = [c["id"] for c in combo]
            if len(set(ids)) != len(ids):
                continue  # cùng một địa điểm không đứng hai chặng trong một lộ trình
            combos_considered += 1

            points = [origin_point] + [(c["lat"], c["lon"]) for c in combo]
            leg_distances = [
                haversine_m(*points[i], *points[i + 1]) * detour for i in range(len(combo))
            ]
            total_distance_m = sum(leg_distances)
            min_total_distance_m = total_distance_m if min_total_distance_m is None else min(min_total_distance_m, total_distance_m)
            if total_distance_m > params.max_distance_m:
                continue
            combos_within_distance += 1

            text_avg = sum(c["text_norm"] for c in combo) / len(combo)
            distance_norm = max(0.0, 1 - total_distance_m / params.max_distance_m)
            walking_min = total_distance_m / icfg["walking_speed_mps"] / 60
            dwell_total = sum(params.dwell_min)
            routes.append(
                {
                    "stops": [
                        _stop_view(i, params.legs[i], c, leg_distances[i], params.dwell_min[i])
                        for i, c in enumerate(combo)
                    ],
                    "total_distance_m": total_distance_m,
                    "walking_time_min": walking_min,
                    "dwell_time_min": dwell_total,
                    "total_time_min": walking_min + dwell_total,
                    "text_avg": text_avg,
                    "distance_norm": distance_norm,
                    "score": weights["text"] * text_avg + weights["geo"] * distance_norm,
                }
            )

    routes.sort(key=lambda r: (-r["score"], r["total_distance_m"], tuple(s["id"] for s in r["stops"])))
    top = routes[: params.limit]
    for rank, route in enumerate(top, start=1):
        route["rank"] = rank

    return {
        "legs": [
            {
                "index": i,
                "query": params.legs[i],
                "query_normalized": " ".join(pool["tokens"]),
                "corrections": pool["corrections"],
                "match_count": pool["match_count"],
                "candidates_considered": len(pool["candidates"]),
                "empty": not pool["candidates"],
                # Tham số hợp lệ để hỏi /api/whynot cho chặng này (radius_m nằm trong allowed_radii_m).
                "whynot_params": {"q": params.legs[i], "radius_m": icfg["search_radius_m"]},
            }
            for i, pool in enumerate(pools)
        ],
        "origin": {"lat": params.lat, "lon": params.lon, "mode": params.origin_mode},
        "max_distance_m": params.max_distance_m,
        "dwell_min": list(params.dwell_min),
        "routes": top,
        "combos_considered": combos_considered,
        "combos_within_distance": combos_within_distance,
        "min_total_distance_m": min_total_distance_m,
        "config": {"detour_factor": detour, "walking_speed_mps": icfg["walking_speed_mps"], "weights": weights},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
