import pytest

from src import db
from src.config import load_app_config, load_campus
from src.importer import import_csv
from src.search import SearchError, parse_params, search

CFG = load_app_config()
REF = load_campus()["reference_point"]
VPP_IDS = {"fx-vpp-hongha", "fx-photo-ngoclan"}


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def run(conn, **args):
    params = parse_params({k: str(v) for k, v in args.items()}, CFG, REF)
    return search(conn, params, CFG)


def ids(result) -> list[str]:
    return [item["id"] for item in result["items"]]


def test_empty_query_browses_by_distance_without_text_scores(conn):
    result = run(conn, radius_m=1000, sort="bm25")
    meta = result["meta"]

    assert ids(result) == ["fx-circle-k", "fx-vpp-hongha", "fx-com-tam", "fx-photo-ngoclan", "fx-pho-dakao"]
    assert (meta["sort_requested"], meta["sort_effective"]) == ("bm25", "distance")
    assert meta["text_match_count"] is None and meta["fts_match"] is None
    assert all(i["bm25_raw"] is None and i["text_norm"] is None and i["score"] is None for i in result["items"])
    distances = [i["distance_m"] for i in result["items"]]
    assert distances == sorted(distances)


def test_radius_filter_and_stage_counts(conn):
    result = run(conn, radius_m=300)

    assert set(ids(result)) == {"fx-circle-k", "fx-vpp-hongha", "fx-com-tam"}
    assert result["meta"]["category_match_count"] == 6
    assert result["meta"]["radius_match_count"] == 3
    assert all(i["distance_m"] <= 300 for i in result["items"])


def test_category_filter(conn):
    result = run(conn, radius_m=2000, category="vpp_photocopy")

    assert set(ids(result)) == VPP_IDS
    assert result["meta"]["category_match_count"] == 2


@pytest.mark.parametrize("q", ["văn phòng phẩm", "van phong pham", "Văn Phòng Phẩm", "VPP"])
def test_accents_case_and_alias_give_same_candidates(conn, q):
    assert set(ids(run(conn, q=q, radius_m=2000))) == VPP_IDS


def test_bm25_mode_puts_best_text_match_first(conn):
    result = run(conn, q="van phong pham", radius_m=2000, sort="bm25")
    scores = [i["bm25_raw"] for i in result["items"]]

    assert ids(result) == ["fx-vpp-hongha", "fx-photo-ngoclan"]
    assert scores == sorted(scores) and all(s < 0 for s in scores)
    assert result["meta"]["text_match_count"] == 2


def test_combined_score_follows_documented_formula(conn):
    result = run(conn, q="van phong pham", radius_m=2000, sort="combined")
    items = result["items"]
    max_s = max(-i["bm25_raw"] for i in items)

    for i in items:
        assert i["text_norm"] == pytest.approx(-i["bm25_raw"] / max_s)
        assert i["geo_norm"] == pytest.approx(1 - i["distance_m"] / 2000)
        assert i["score"] == pytest.approx(0.6 * i["text_norm"] + 0.4 * i["geo_norm"])
    assert max(i["text_norm"] for i in items) == pytest.approx(1.0)
    assert [i["score"] for i in items] == sorted((i["score"] for i in items), reverse=True)


@pytest.mark.parametrize("q", ["", "van phong pham", "an uong"])
def test_three_modes_share_the_same_candidate_set(conn, q):
    results = [run(conn, q=q, radius_m=2000, sort=s) for s in ("distance", "bm25", "combined")]

    assert len({frozenset(ids(r)) for r in results}) == 1
    assert len({r["meta"]["radius_match_count"] for r in results}) == 1


def test_moving_the_origin_recomputes_distances(conn):
    result = run(conn, lat=10.769357, lon=106.6821769, radius_m=300, origin_mode="simulated")

    assert ids(result) == ["fx-pho-dakao"]
    assert result["items"][0]["distance_m"] == pytest.approx(0, abs=0.01)
    assert result["meta"]["origin"]["mode"] == "simulated"


def test_distance_ties_break_by_id(tmp_path, fixture_rows, write_csv):
    circle_k = next(r for r in fixture_rows if r["id"] == "fx-circle-k")
    rows = fixture_rows + [dict(circle_k, id="fx-aaa-clone", name="Bản sao cùng tọa độ")]
    conn = db.connect(tmp_path / "ties.db")
    try:
        assert import_csv(conn, write_csv(rows)).errors == []
        assert ids(run(conn, radius_m=300))[:2] == ["fx-aaa-clone", "fx-circle-k"]
    finally:
        conn.close()


def test_query_without_match_is_empty(conn):
    result = run(conn, q="khongtontai", radius_m=2000)

    assert result["items"] == []
    assert result["meta"]["text_match_count"] == 0


@pytest.mark.parametrize(
    "q",
    ['"', 'pho"', "pho OR 1=1", "NEAR(pho", "*", "<script>alert(1)</script>", "'; DROP TABLE pois; --"],
)
def test_special_characters_are_treated_as_plain_text(conn, q):
    result = run(conn, q=q, radius_m=2000)

    assert isinstance(result["items"], list)
    assert conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0] == 6


def test_limit_is_applied_after_ranking(conn):
    result = run(conn, radius_m=1000, limit=2)

    assert ids(result) == ["fx-circle-k", "fx-vpp-hongha"]
    assert (result["meta"]["returned_count"], result["meta"]["radius_match_count"]) == (2, 5)


def test_missing_origin_defaults_to_reference_point():
    params = parse_params({}, CFG, REF)

    assert (params.lat, params.lon, params.origin_mode) == (REF["lat"], REF["lon"], "reference")
    assert params.radius_m == CFG["search"]["default_radius_m"]


@pytest.mark.parametrize(
    "args, message",
    [
        ({"radius_m": "123"}, "radius_m phải là một trong"),
        ({"radius_m": "abc"}, "số nguyên"),
        ({"lat": "10.7"}, "cần cả lat và lon"),
        ({"lat": "nan", "lon": "106.6"}, "hữu hạn"),
        ({"lat": "91", "lon": "106.6"}, "ngoài miền"),
        ({"q": "x" * 121}, "tối đa 120"),
        ({"sort": "random"}, "sort phải thuộc"),
        ({"limit": "0"}, "limit phải từ"),
        ({"limit": "101"}, "limit phải từ"),
        ({"category": "khach_san"}, "category không hợp lệ"),
        ({"origin_mode": "x"}, "origin_mode phải thuộc"),
    ],
)
def test_invalid_parameters_raise(args, message):
    with pytest.raises(SearchError, match=message):
        parse_params(args, CFG, REF)
