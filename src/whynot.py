"""Trả lời câu hỏi "Vì sao không có?" (why-not) cho truy vấn không gian–từ khóa top-k.

Người dùng chỉ ra một POI m mà họ mong đợi nhưng không nằm trong top-k. Module này:
1. chẩn đoán bước của pipeline loại m (thiếu từ khóa, sai danh mục, ngoài bán kính, hạng thấp),
   dựa đúng các bước của src.search;
2. liệt kê các truy vấn đã sửa Q' đưa m vào top-k' và chấm penalty = λ·Δk + (1 − λ)·Δq, theo
   hướng sửa truy vấn của He & Lo (ICDE 2012) và Chen et al. (ICDE 2015, 2016);
3. chạy lại từng đề xuất trả về bằng chính search() để xác nhận; không đưa đề xuất suy đoán.

Corpus nhỏ nên vét cạn: mỗi tổ hợp (từ khóa, bán kính, danh mục) truy xuất một lần, các chế độ
xếp hạng và α chỉ sắp lại trong bộ nhớ. Ở chế độ kết hợp, điểm α·t + (1 − α)·g tuyến tính theo α
nên hạng của m chỉ đổi tại giao điểm giữa đường của m và đường của POI khác; module quét các giao
điểm đó để lấy các giá trị α tốt nhất thay vì dò lưới.

Từ thêm vào truy vấn (keyword adaption) chỉ lấy từ tên của m: người dùng hiểu được "thêm từ trong
tên quán", còn tag nguồn (thường tiếng Anh như "brunch") thì không.
"""
import dataclasses
import itertools
import re
import sqlite3
import time

from src.geo import haversine_m
from src.normalize import analyze
from src.search import (
    SearchParams,
    combined_weights,
    fts_expression,
    query_tokens,
    rank_items,
    retrieve,
    score_items,
    search,
)

SORT_LABELS = {"distance": "Gần nhất", "bm25": "Đúng từ khóa", "combined": "Kết hợp"}
# Chiến lược sửa đơn lẻ dùng khi đánh giá: (chiều chính, các chiều được phép đi kèm).
# "k" luôn được phép vì mọi truy vấn sửa đều có thể kèm tăng k (He & Lo, ICDE 2012).
STRATEGIES = {
    "S1": ("k", {"k"}),
    "S2": ("sort", {"sort", "k"}),
    "S3": ("alpha", {"alpha", "sort", "k"}),
    "S4": ("radius", {"radius", "k"}),
    "S5": ("category", {"category", "k"}),
    "S6": ("drop_tokens", {"drop_tokens", "k"}),
    "S7": ("add_token", {"add_token", "drop_tokens", "k"}),
}
STRATEGY_NAMES = {
    "S1": "Tăng k",
    "S2": "Đổi chế độ xếp hạng",
    "S3": "Chỉnh trọng số α",
    "S4": "Nới bán kính",
    "S5": "Bỏ lọc danh mục",
    "S6": "Bỏ từ khóa",
    "S7": "Thêm/thay từ trong tên",
    "ALL": "Kết hợp theo penalty",
}
_WORD_EDGE = re.compile(r"^\W+|\W+$")


class PoiNotFound(LookupError):
    """poi_id không có trong DB (API trả 404)."""


def fmt_m(m: float) -> str:
    return f"{m:.0f} m" if m < 1000 else f"{m / 1000:.2f} km"


def fmt_radius(m: int) -> str:
    return f"{m} m" if m < 1000 else f"{m / 1000:g} km"


def quoted(words) -> str:
    return ", ".join(f"“{w}”" for w in words)


def in_strategy(dims: set[str], strategy: str) -> bool:
    primary, allowed = STRATEGIES[strategy]
    return primary in dims and dims <= allowed


# ---------- Từ gốc có dấu ----------

def words_of(text: str | None) -> list[str]:
    words = (_WORD_EDGE.sub("", w) for w in (text or "").split())
    return [w for w in words if w]


def word_map(text: str | None) -> dict[str, str]:
    """token → từ gốc có dấu, khi từ gốc cho đúng một token (để hiển thị "sáng" thay vì "sang")."""
    out: dict[str, str] = {}
    for word in words_of(text):
        tokens = analyze(word)
        if len(tokens) == 1:
            out.setdefault(tokens[0], word)
    return out


def rebuild_query(q: str, kept: tuple[str, ...], added_word: str | None = None) -> str:
    """Truy vấn sửa viết bằng từ gốc của người dùng (giữ dấu) khi có thể, nếu không thì bằng token."""
    kept_set = set(kept)
    chosen = [w for w in words_of(q) if analyze(w) and all(t in kept_set for t in analyze(w))]
    if added_word:
        chosen.append(added_word)
    text = " ".join(chosen)
    return text if analyze(text) == list(kept) else " ".join(kept)


# ---------- Văn bản đã lập chỉ mục của POI ----------

def indexed_document(conn: sqlite3.Connection, poi_id: str) -> dict:
    """Các cột FTS của POI (đã chuẩn hóa, không dấu): đúng thứ mà truy vấn được so khớp."""
    row = conn.execute("SELECT name, category, description, tags FROM poi_fts WHERE poi_id = ?", (poi_id,)).fetchone()
    return dict(row) if row else {"name": "", "category": "", "description": "", "tags": ""}


def doc_has_token(conn: sqlite3.Connection, poi_id: str, token: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM poi_fts WHERE poi_fts MATCH ? AND poi_id = ?", (fts_expression([token]), poi_id)
    ).fetchone()
    return row is not None


def document_frequency(conn: sqlite3.Connection, token: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM poi_fts WHERE poi_fts MATCH ?", (fts_expression([token]),)).fetchone()[0]


def addable_tokens(conn: sqlite3.Connection, poi_id: str, query_tokens_: list[str], limit: int) -> list[str]:
    """Từ trong tên POI chưa có trong truy vấn, hiếm nhất trước (DF nhỏ ~ IDF lớn)."""
    name = indexed_document(conn, poi_id)["name"] or ""
    words = dict.fromkeys(name.split())
    candidates = [w for w in words if w not in query_tokens_ and len(w) >= 2 and not w.isdigit()]
    return sorted(candidates, key=lambda w: (document_frequency(conn, w), w))[:limit]


# ---------- Chẩn đoán ----------

def diagnose(conn, poi, tokens, params: SearchParams, cfg, ranked, rank, k, sort_effective, distance, shown) -> tuple[list[dict], list[str]]:
    """Trả về (các lý do theo thứ tự pipeline, các token truy vấn mà POI thiếu).

    Mỗi lý do có `short` (một câu cho giao diện) và `message` (đầy đủ, dùng trong báo cáo).
    """
    labels = {c["id"]: c["label"] for c in cfg["categories"]}
    reasons = []
    missing = [t for t in dict.fromkeys(tokens) if not doc_has_token(conn, poi["id"], t)]
    # Khớp AND: thiếu một từ là bị loại. Khớp OR (chữ đọc từ ảnh): chỉ bị loại khi thiếu mọi từ.
    text_blocked = bool(missing) and (params.match == "all" or len(missing) == len(set(tokens)))
    if text_blocked:
        words = [shown.get(t, t) for t in missing]
        reasons.append(
            {
                "code": "TEXT",
                "missing_tokens": missing,
                "missing_words": words,
                "short": f"Dữ liệu của địa điểm không có từ {quoted(words)}.",
                "message": f"Văn bản được lập chỉ mục của địa điểm không có từ {quoted(words)}. Các từ trong truy vấn "
                "nối bằng AND nên thiếu một từ là bị loại ngay ở bước khớp văn bản (FTS5).",
            }
        )
    if params.category and poi["category"] != params.category:
        text = (
            f"Địa điểm thuộc danh mục “{labels.get(poi['category'], poi['category'])}”, "
            f"còn bạn đang lọc “{labels.get(params.category, params.category)}”."
        )
        reasons.append({"code": "CATEGORY", "short": text, "message": text})
    if distance > params.radius_m:
        reasons.append(
            {
                "code": "RADIUS",
                "distance_m": distance,
                "short": f"Cách {fmt_m(distance)}, bạn đang tìm trong {fmt_radius(params.radius_m)}.",
                "message": f"Địa điểm cách vị trí gốc {fmt_m(distance)} (đường chim bay), ngoài bán kính {fmt_radius(params.radius_m)}.",
            }
        )
    if not reasons and rank is not None and rank > k:
        reasons.append(rank_reason(ranked, rank, k, sort_effective))
    return reasons, missing


def rank_reason(ranked: list[dict], rank: int, k: int, sort_effective: str) -> dict:
    m, kth = ranked[rank - 1], ranked[k - 1]
    head = f"Địa điểm có khớp nhưng đứng hạng {rank}/{len(ranked)} theo chế độ {SORT_LABELS[sort_effective]}"
    if sort_effective == "distance":
        why = f"xa hơn: cách {fmt_m(m['distance_m'])}, còn hạng {k} cách {fmt_m(kth['distance_m'])}"
        tail = f": cách {fmt_m(m['distance_m'])}, trong khi hạng {k} ({kth['name']}) chỉ cách {fmt_m(kth['distance_m'])}."
    elif sort_effective == "bm25":
        why = "khớp từ khóa yếu hơn các địa điểm đứng trước"
        tail = (
            f": BM25 {m['bm25_raw']:.3f} so với hạng {k} ({kth['name']}) là {kth['bm25_raw']:.3f} "
            "(càng âm càng khớp; tên có trọng số 2)."
        )
    else:
        why = f"điểm kết hợp thấp hơn ({m['score']:.2f} so với {kth['score']:.2f} của hạng {k})"
        tail = (
            f": điểm kết hợp {m['score']:.3f} so với hạng {k} ({kth['name']}) là {kth['score']:.3f}; "
            f"điểm văn bản {m['text_norm']:.2f} so với {kth['text_norm']:.2f}, "
            f"điểm khoảng cách {m['geo_norm']:.2f} so với {kth['geo_norm']:.2f}."
        )
    components = ("distance_m", "bm25_raw", "text_norm", "geo_norm", "score")
    return {
        "code": "RANK",
        "rank": rank,
        "candidates": len(ranked),
        "target": {c: m[c] for c in components},
        "kth": {"name": kth["name"], **{c: kth[c] for c in components}},
        "short": f"Có trong kết quả nhưng đứng hạng {rank}, vì {why}.",
        "message": head + tail,
    }


def pipeline_steps(tokens, params: SearchParams, reasons: list[dict], rank: int | None, k: int) -> list[dict]:
    """Trạng thái 4 bước của pipeline cho giao diện: pass / fail / skip (không áp dụng) / blocked."""
    failed = {r["code"] for r in reasons}
    filters_ok = not (failed & {"TEXT", "CATEGORY", "RADIUS"})
    return [
        {"code": "TEXT", "label": "Khớp từ khóa", "status": "skip" if not tokens else ("fail" if "TEXT" in failed else "pass")},
        {"code": "CATEGORY", "label": "Danh mục", "status": "skip" if not params.category else ("fail" if "CATEGORY" in failed else "pass")},
        {"code": "RADIUS", "label": "Bán kính", "status": "fail" if "RADIUS" in failed else "pass"},
        {
            "code": "RANK",
            "label": f"{k} kết quả đầu",
            "status": "blocked" if not filters_ok else ("pass" if rank is not None and rank <= k else "fail"),
        },
    ]


# ---------- Liệt kê truy vấn sửa ----------

def change(dim: str, old, new, cost: float, text: str) -> dict:
    return {"dim": dim, "from": old, "to": new, "cost": cost, "text": text}


def token_variants(conn, tokens, missing, poi_id, wcfg, shown, name_words) -> list[tuple[tuple, list, str | None]]:
    """(từ khóa của Q', các thay đổi, từ gốc được thêm) gồm: giữ nguyên, bỏ bớt từ, thêm/thay một từ trong tên POI."""
    costs = wcfg["costs"]
    distinct = list(dict.fromkeys(tokens))
    n = len(distinct)
    variants = [(tuple(tokens), [], None)]
    droppable = distinct if n <= wcfg["max_drop_tokens"] else missing
    for size in range(1, len(droppable) + 1):
        for dropped in itertools.combinations(droppable, size):
            kept = tuple(t for t in tokens if t not in dropped)
            words = [shown.get(t, t) for t in dropped]
            variants.append((kept, [change("drop_tokens", distinct, list(dropped), costs["drop_token"] * size / n, f"Bỏ từ {quoted(words)}")], None))
    for token in addable_tokens(conn, poi_id, distinct, wcfg["add_token_candidates"]):
        word = name_words.get(token, token)
        add = change("add_token", None, token, costs["add_token"] / (n + 1), f"Thêm từ “{word}” (có trong tên)")
        variants.append((tuple(tokens) + (token,), [add], word))
        if missing:
            kept = tuple(t for t in tokens if t not in missing)
            words = [shown.get(t, t) for t in missing]
            drop = change("drop_tokens", distinct, missing, costs["drop_token"] * len(missing) / n, f"Bỏ từ {quoted(words)}")
            variants.append((kept + (token,), [drop, add], word))
    unique: dict[tuple, tuple] = {}
    for kept, changes, word in variants:
        cost = sum(c["cost"] for c in changes)
        if kept not in unique or cost < sum(c["cost"] for c in unique[kept][0]):
            unique[kept] = (changes, word)
    return [(kept, changes, word) for kept, (changes, word) in unique.items()]


def alpha_candidates(items: list[dict], target_id: str, alpha0: float) -> list[float]:
    """Các α (ngoài α0) mà tại đó số POI xếp trên m giảm so với mọi α gần α0 hơn.

    diff_i(α) = (g_i − g_m) + α·[(t_i − g_i) − (t_m − g_m)] đổi dấu tại b_i = −c_i / e_i. Quét giao
    điểm ra hai phía của α0; mỗi lần số POI trên m đạt mức thấp mới thì lấy một điểm ngay bên trong
    khoảng kế tiếp. Hạng thật tại các điểm này được tính lại bằng rank_items (xử lý cả trường hợp hòa).
    """
    m = next(i for i in items if i["id"] == target_id)
    crossings = []
    for it in items:
        if it["id"] == target_id:
            continue
        c = it["geo_norm"] - m["geo_norm"]
        e = (it["text_norm"] - it["geo_norm"]) - (m["text_norm"] - m["geo_norm"])
        if e != 0 and 0 < -c / e < 1:
            # Khi α tăng qua b: e > 0 thì POI này vượt lên trên m (+1), e < 0 thì tụt xuống (−1).
            crossings.append((-c / e, 1 if e > 0 else -1))

    result = []
    for direction in (1, -1):
        side = sorted((b, s) for b, s in crossings if (b > alpha0 if direction > 0 else b < alpha0))
        if direction < 0:
            side.reverse()
        above, best, i = 0, 0, 0
        while i < len(side):
            b = side[i][0]
            while i < len(side) and side[i][0] == b:
                above += side[i][1] * direction
                i += 1
            if above < best:
                best = above
                nxt = side[i][0] if i < len(side) else (1.0 if direction > 0 else 0.0)
                result.append(point_inside(b, nxt))
    return result


def point_inside(b: float, nxt: float) -> float:
    """Điểm trong khoảng mở (b, nxt), sát b, làm tròn 3 chữ số nếu vẫn nằm trong khoảng."""
    lo, hi = min(b, nxt), max(b, nxt)
    step = min(0.001, (hi - lo) / 2)
    value = b + step if nxt > b else b - step
    rounded = round(value, 3)
    return rounded if lo < rounded < hi else value


def alpha_text(alpha0: float, a: float) -> str:
    direction = "Ưu tiên khoảng cách hơn" if a < alpha0 else "Ưu tiên từ khóa hơn"
    return f"{direction} (trọng số từ khóa {alpha0:g} → {a:g})"


def enumerate_options(conn, params: SearchParams, poi, tokens, missing, cfg, k: int, max_changes: int, shown, name_words) -> list[dict]:
    """Mọi truy vấn sửa (≤ max_changes thay đổi, chưa tính k) đưa được POI vào kết quả."""
    wcfg = cfg["whynot"]
    costs = wcfg["costs"]
    allowed = cfg["search"]["allowed_radii_m"]
    labels = {c["id"]: c["label"] for c in cfg["categories"]}
    weights0 = combined_weights(params.alpha, cfg)
    alpha0 = weights0["text"]

    radius_options = [(params.radius_m, [])]
    for r in allowed:
        if r > params.radius_m:
            steps = allowed.index(r) - allowed.index(params.radius_m)
            radius_options.append(
                (r, [change("radius", params.radius_m, r, costs["radius"] * steps / (len(allowed) - 1), f"Nới bán kính lên {fmt_radius(r)}")])
            )
    category_options = [(params.category, [])]
    if params.category:
        category_options.append(
            (None, [change("category", params.category, None, costs["category"], f"Bỏ lọc “{labels.get(params.category, params.category)}”")])
        )

    options = []
    for (kept, tchanges, added_word), (radius, rchanges), (category, cchanges) in itertools.product(
        token_variants(conn, tokens, missing, poi["id"], wcfg, shown, name_words), radius_options, category_options
    ):
        base_changes = tchanges + rchanges + cchanges
        if len(base_changes) > max_changes:
            continue
        items, _ = retrieve(conn, list(kept), params.lat, params.lon, radius, category, cfg, params.match)
        if not any(i["id"] == poi["id"] for i in items):
            continue
        has_text = bool(kept)
        q = params.q if kept == tuple(tokens) else rebuild_query(params.q, kept, added_word)
        for sort in ("distance", "bm25", "combined") if has_text else (params.sort,):
            changes = list(base_changes)
            if sort != params.sort:
                changes.append(change("sort", params.sort, sort, costs["sort"], f"Xếp theo “{SORT_LABELS[sort]}”"))
            if len(changes) > max_changes:
                continue
            alphas = [(params.alpha, weights0, [])]
            if sort == "combined" and has_text and len(changes) < max_changes:
                span = max(alpha0, 1 - alpha0)
                for a in alpha_candidates(items, poi["id"], alpha0):
                    alphas.append(
                        (a, {"text": a, "geo": 1 - a}, [change("alpha", alpha0, a, costs["alpha"] * abs(a - alpha0) / span, alpha_text(alpha0, a))])
                    )
            for alpha, weights, achanges in alphas:
                score_items(items, weights)
                ranked, _ = rank_items(items, sort, has_text)
                ids = [i["id"] for i in ranked]
                rank = ids.index(poi["id"]) + 1
                options.append(
                    {
                        "tokens": kept,
                        "q": q,
                        "radius_m": radius,
                        "category": category,
                        "sort": sort,
                        "alpha": alpha,
                        "changes": changes + achanges,
                        "rank": rank,
                        "k_new": max(k, rank),
                        "top_ids": ids[: max(k, rank)],
                    }
                )
    return options


def score_options(options: list[dict], original_top: list[str], rank0: int | None, k: int, total: int, wcfg: dict) -> None:
    """Gắn Δk, Δq, penalty, tỷ lệ giữ kết quả cũ và họ chiến lược cho từng phương án."""
    lam = wcfg["lambda"]
    # Chuẩn hóa Δk theo He & Lo: chỉ tăng k (giữ nguyên truy vấn) có Δk = 1.
    denom = (rank0 - k) if rank0 is not None and rank0 > k else max(1, total - k)
    for o in options:
        o["delta_k"] = min(1.0, (o["k_new"] - k) / denom)
        o["delta_q"] = min(1.0, sum(c["cost"] for c in o["changes"]))
        o["penalty"] = lam * o["delta_k"] + (1 - lam) * o["delta_q"]
        o["retained"] = len(set(original_top) & set(o["top_ids"])) / len(original_top) if original_top else None
        dims = {c["dim"] for c in o["changes"]} | ({"k"} if o["k_new"] > k else set())
        o["dims"] = dims
        o["family"] = "+".join(sorted(dims)) or "none"


def option_order(o: dict):
    return (o["penalty"], -(o["retained"] if o["retained"] is not None else 0), len(o["dims"]), o["k_new"])


# ---------- API ----------

def why_not(conn: sqlite3.Connection, params: SearchParams, poi_id: str, cfg: dict, k: int | None = None, return_all: bool = False) -> dict:
    started = time.perf_counter()
    wcfg = cfg["whynot"]
    k = k or wcfg["k"]
    labels = {c["id"]: c["label"] for c in cfg["categories"]}
    poi = conn.execute("SELECT * FROM pois WHERE id = ?", (poi_id,)).fetchone()
    if poi is None:
        raise PoiNotFound(poi_id)

    tokens, corrections = query_tokens(conn, params.q, params.spell, cfg)
    shown = word_map(params.q)
    name_words = word_map(poi["name"])
    weights0 = combined_weights(params.alpha, cfg)
    items, _ = retrieve(conn, tokens, params.lat, params.lon, params.radius_m, params.category, cfg, params.match)
    score_items(items, weights0)
    ranked, sort_effective = rank_items(items, params.sort, bool(tokens))
    ids = [i["id"] for i in ranked]
    rank0 = ids.index(poi_id) + 1 if poi_id in ids else None
    original_top = ids[:k]
    distance = haversine_m(params.lat, params.lon, poi["lat"], poi["lon"])
    reasons, missing = diagnose(conn, poi, tokens, params, cfg, ranked, rank0, k, sort_effective, distance, shown)
    in_top_k = rank0 is not None and rank0 <= k
    if in_top_k:
        text = f"Địa điểm đang đứng hạng {rank0}, đã nằm trong {k} kết quả đầu."
        reasons = [{"code": "IN_TOP_K", "short": text, "message": text}]
    steps = pipeline_steps(tokens, params, reasons, rank0, k)

    # Mỗi bộ lọc chặn POI cần ít nhất một thay đổi, nên nới giới hạn khi POI bị chặn bởi nhiều bộ lọc.
    max_changes = max(wcfg["max_changes"], sum(1 for r in reasons if r["code"] in ("TEXT", "CATEGORY", "RADIUS")))
    suggestions, options, unverified = [], [], 0
    if not in_top_k:
        total = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
        options = enumerate_options(conn, params, poi, tokens, missing, cfg, k, max_changes, shown, name_words)
        score_options(options, original_top, rank0, k, total, wcfg)
        options.sort(key=option_order)
        best_by_family: dict[str, dict] = {}
        for o in options:
            best_by_family.setdefault(o["family"], o)
        for o in sorted(best_by_family.values(), key=option_order):
            if len(suggestions) == wcfg["max_suggestions"]:
                break
            if verify(conn, params, poi_id, o, cfg):
                suggestions.append(suggestion_view(o, k))
            else:
                unverified += 1

    doc = indexed_document(conn, poi_id)
    result = {
        "target": {
            "id": poi["id"],
            "name": poi["name"],
            "category": poi["category"],
            "category_label": labels.get(poi["category"], poi["category"]),
            "address": poi["address"],
            "lat": poi["lat"],
            "lon": poi["lon"],
            "distance_m": distance,
            "indexed_text": doc,
            "source_tags": poi["tags"],
        },
        "query": {
            "q": params.q,
            "query_normalized": " ".join(tokens),
            "corrections": corrections,
            "radius_m": params.radius_m,
            "category": params.category,
            "sort": params.sort,
            "sort_effective": sort_effective,
            "alpha": params.alpha,
            "weights": weights0,
            "k": k,
        },
        "in_top_k": in_top_k,
        "rank": rank0,
        "candidate_count": len(ranked),
        "original_top_k": [{"id": i["id"], "name": i["name"]} for i in ranked[:k]],
        "steps": steps,
        "reasons": reasons,
        "suggestions": suggestions,
        "options_considered": len(options),
        "unverified_dropped": unverified,
        "penalty": {"lambda": wcfg["lambda"], "costs": wcfg["costs"], "max_changes": max_changes},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    if return_all:
        result["all_options"] = options
    return result


def verify(conn, params: SearchParams, poi_id: str, option: dict, cfg: dict) -> bool:
    """Chạy lại truy vấn sửa bằng search() của API; đúng khi POI nằm đúng hạng đã tính, trong top-k'."""
    limit = option["k_new"]
    if limit > cfg["search"]["max_limit"]:
        return False
    revised = dataclasses.replace(
        params,
        q=option["q"],
        radius_m=option["radius_m"],
        category=option["category"],
        sort=option["sort"],
        alpha=option["alpha"],
        limit=limit,
    )
    ids = [i["id"] for i in search(conn, revised, cfg)["items"]]
    return poi_id in ids and ids.index(poi_id) + 1 == option["rank"]


def suggestion_view(o: dict, k: int) -> dict:
    changes = [{key: c[key] for key in ("dim", "from", "to", "text")} for c in o["changes"]]
    if o["k_new"] > k:
        changes.append({"dim": "k", "from": k, "to": o["k_new"], "text": f"Xem {o['k_new']} kết quả đầu thay vì {k}"})
    return {
        "family": o["family"],
        "changes": changes,
        "params": {
            "q": o["q"],
            "radius_m": o["radius_m"],
            "category": o["category"],
            "sort": o["sort"],
            "alpha": o["alpha"],
            "k": o["k_new"],
        },
        "rank": o["rank"],
        "delta_k": round(o["delta_k"], 4),
        "delta_q": round(o["delta_q"], 4),
        "penalty": round(o["penalty"], 4),
        "retained": o["retained"],
        "verified": True,
    }
