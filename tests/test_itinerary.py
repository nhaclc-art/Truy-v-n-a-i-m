import pytest
from werkzeug.datastructures import MultiDict

from src import db
from src.config import load_app_config, load_campus
from src.geo import haversine_m
from src.itinerary import ItineraryError, leg_pool, parse_itinerary_params, plan

CFG = load_app_config()
REF = load_campus()["reference_point"]


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def args(**kwargs):
    """MultiDict giống request.args của Flask; 'stop' và 'dwell_min' nhận list cho nhiều giá trị."""
    items = []
    for key, value in kwargs.items():
        if isinstance(value, list):
            items.extend((key, str(v)) for v in value)
        else:
            items.append((key, str(value)))
    return MultiDict(items)


def params(**kwargs):
    return parse_itinerary_params(args(**kwargs), CFG, REF)


def ids_of(route) -> list[str]:
    return [s["id"] for s in route["stops"]]


# ---------- parse_itinerary_params ----------


def test_parses_legs_origin_and_defaults():
    p = params(stop=["van phong pham", "com"])

    assert p.legs == ("van phong pham", "com")
    assert (p.lat, p.lon, p.origin_mode) == (REF["lat"], REF["lon"], "reference")
    assert p.max_distance_m == CFG["itinerary"]["default_max_distance_m"]
    assert p.dwell_min == (CFG["itinerary"]["default_dwell_min"],) * 2
    assert p.limit == CFG["itinerary"]["max_results"]


def test_custom_origin_max_distance_and_limit():
    p = params(stop=["a", "b"], lat=10.77, lon=106.68, max_distance_m=1500, limit=1)

    assert (p.lat, p.lon, p.origin_mode) == (10.77, 106.68, "custom")
    assert p.max_distance_m == 1500 and p.limit == 1


def test_single_dwell_min_applies_to_every_leg():
    p = params(stop=["a", "b", "c"], dwell_min=[30])
    assert p.dwell_min == (30, 30, 30)


def test_one_dwell_min_per_leg():
    p = params(stop=["a", "b"], dwell_min=[30, 90])
    assert p.dwell_min == (30, 90)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"stop": ["only one"]}, "chặng"),
        ({"stop": ["a", "b", "c", "d", "e"]}, "chặng"),
        ({"stop": ["a", "b"], "max_distance_m": "0"}, "max_distance_m"),
        ({"stop": ["a", "b"], "max_distance_m": "abc"}, "số nguyên"),
        ({"stop": ["a", "b"], "dwell_min": [10, 20, 30]}, "dwell_min"),
        ({"stop": ["a", "b"], "dwell_min": ["x"]}, "số nguyên"),
        ({"stop": ["a", "b"], "dwell_min": [-5]}, "≥ 0"),
        ({"stop": ["a", "b"], "limit": "11"}, "limit"),
        ({"stop": ["a", "b"], "lat": "10.7"}, "cần cả lat"),
        ({"stop": ["x" * 121, "b"]}, "ký tự"),
    ],
)
def test_invalid_parameters_raise(kwargs, message):
    with pytest.raises(ItineraryError, match=message):
        params(**kwargs)


# ---------- leg_pool ----------


def test_leg_pool_matches_by_category_label_and_sorts_by_text_then_distance(conn):
    pool = leg_pool(conn, CFG, "photocopy", REF["lat"], REF["lon"])

    assert pool["tokens"] == ["photocopy"]
    assert {c["id"] for c in pool["candidates"]} == {"fx-vpp-hongha", "fx-photo-ngoclan"}


def test_leg_pool_is_empty_when_nothing_matches(conn):
    pool = leg_pool(conn, CFG, "khongtontai", REF["lat"], REF["lon"])
    assert pool["candidates"] == [] and pool["match_count"] == 0


def test_leg_pool_caps_at_max_candidates_per_leg(conn):
    small_cfg = {**CFG, "itinerary": {**CFG["itinerary"], "max_candidates_per_leg": 1}}
    pool = leg_pool(conn, small_cfg, "an uong", REF["lat"], REF["lon"])
    assert len(pool["candidates"]) == 1


# ---------- plan ----------


def test_plan_finds_the_single_valid_route_and_computes_distance_with_detour_factor(conn):
    # "hong ha" khớp đúng một địa điểm qua tên (VPP Hồng Hà); "com" khớp đúng fx-com-tam qua tags.
    p = params(stop=["hong ha", "com"], max_distance_m=100_000)
    result = plan(conn, CFG, p)

    assert len(result["routes"]) == 1
    route = result["routes"][0]
    assert ids_of(route) == ["fx-vpp-hongha", "fx-com-tam"]
    assert route["rank"] == 1

    detour = CFG["itinerary"]["detour_factor"]
    leg0 = haversine_m(REF["lat"], REF["lon"], 10.763157, 106.6821769) * detour
    leg1 = haversine_m(10.763157, 106.6821769, 10.761357, 106.6848769) * detour
    assert route["stops"][0]["distance_from_prev_m"] == pytest.approx(leg0)
    assert route["stops"][1]["distance_from_prev_m"] == pytest.approx(leg1)
    assert route["total_distance_m"] == pytest.approx(leg0 + leg1)
    assert route["walking_time_min"] == pytest.approx(route["total_distance_m"] / CFG["itinerary"]["walking_speed_mps"] / 60)
    assert route["dwell_time_min"] == 2 * CFG["itinerary"]["default_dwell_min"]
    assert route["total_time_min"] == pytest.approx(route["walking_time_min"] + route["dwell_time_min"])
    assert result["combos_considered"] == 1 and result["combos_within_distance"] == 1


def test_plan_enumerates_all_combinations_across_three_legs(conn):
    # "photocopy" khớp 2, "an uong" khớp 2, "tien loi" khớp 1 (khác danh mục nên không trùng id).
    p = params(stop=["photocopy", "an uong", "tien loi"], max_distance_m=100_000, limit=10)
    result = plan(conn, CFG, p)

    assert result["combos_considered"] == 4
    assert result["combos_within_distance"] == 4
    assert len(result["routes"]) == 4
    scores = [r["score"] for r in result["routes"]]
    assert scores == sorted(scores, reverse=True)
    assert all(len(set(ids_of(r))) == 3 for r in result["routes"])


def test_plan_filters_out_routes_over_the_distance_budget_but_reports_the_shortest(conn):
    p = params(stop=["hong ha", "com"], max_distance_m=1)
    result = plan(conn, CFG, p)

    assert result["routes"] == []
    assert result["combos_considered"] == 1
    assert result["combos_within_distance"] == 0
    assert result["min_total_distance_m"] > 1


def test_plan_skips_routes_that_reuse_the_same_place_across_legs(conn):
    # "circle k" và "tien loi" cùng chỉ khớp fx-circle-k (danh mục tien_loi duy nhất trong fixture).
    p = params(stop=["circle k", "tien loi"], max_distance_m=100_000)
    result = plan(conn, CFG, p)

    assert result["routes"] == []
    assert result["combos_considered"] == 0
    assert result["min_total_distance_m"] is None
    assert not any(leg["empty"] for leg in result["legs"])


def test_plan_reports_empty_legs_without_crashing(conn):
    p = params(stop=["van phong pham", "khongtontai"], max_distance_m=100_000)
    result = plan(conn, CFG, p)

    assert result["routes"] == []
    assert result["legs"][0]["empty"] is False and result["legs"][1]["empty"] is True
    assert result["legs"][1]["whynot_params"] == {"q": "khongtontai", "radius_m": CFG["itinerary"]["search_radius_m"]}


def test_plan_applies_typo_correction_per_leg(conn):
    # Giống bộ sửa lỗi gõ của tìm kiếm thường: "photocoppy" -> "photocopy" (khớp cả 2 địa điểm
    # vpp_photocopy, vì nhãn danh mục "... / photocopy" cũng có token "photocopy").
    p = params(stop=["photocoppy", "com"], max_distance_m=100_000)
    result = plan(conn, CFG, p)

    assert result["legs"][0]["query_normalized"] == "photocopy"
    assert result["legs"][0]["corrections"] == [{"from": "photocoppy", "to": "photocopy", "kind": "edit"}]
    assert len(result["routes"]) == 2
    assert {ids_of(r)[0] for r in result["routes"]} == {"fx-vpp-hongha", "fx-photo-ngoclan"}
    assert {ids_of(r)[1] for r in result["routes"]} == {"fx-com-tam"}
