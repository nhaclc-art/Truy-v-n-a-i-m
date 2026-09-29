import pytest

from src import db
from src.config import load_app_config, load_campus
from src.search import parse_params, search
from src.whynot import PoiNotFound, alpha_candidates, in_strategy, point_inside, rebuild_query, why_not
from src.whynot_eval import questions_from_qrels, run_question, summarize_rows

CFG = load_app_config()
REF = load_campus()["reference_point"]


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def params(**args):
    return parse_params({k: str(v) for k, v in args.items()}, CFG, REF)


def ask(conn, poi_id, k=None, **args):
    return why_not(conn, params(**args), poi_id, CFG, k)


def codes(result) -> list[str]:
    return [r["code"] for r in result["reasons"]]


def assert_suggestions_hold(conn, result, poi_id):
    """Chạy lại độc lập từng đề xuất: POI phải nằm trong top-k' của truy vấn đã sửa."""
    assert result["suggestions"], "phải có ít nhất một đề xuất"
    assert result["unverified_dropped"] == 0
    for s in result["suggestions"]:
        p = s["params"]
        args = {"q": p["q"], "radius_m": p["radius_m"], "sort": p["sort"], "limit": p["k"]}
        if p["category"]:
            args["category"] = p["category"]
        if p["alpha"] is not None:
            args["alpha"] = p["alpha"]
        ids = [i["id"] for i in search(conn, params(**args), CFG)["items"]]
        assert poi_id in ids and ids.index(poi_id) + 1 == s["rank"] <= p["k"]
        assert s["verified"] is True


def test_missing_keywords_are_reported_and_fixed(conn):
    result = ask(conn, "fx-vpp-hongha", q="tai lieu", radius_m=1000)

    assert codes(result) == ["TEXT"]
    assert result["reasons"][0]["missing_tokens"] == ["tai", "lieu"]
    assert result["rank"] is None and result["in_top_k"] is False
    assert "van phong pham" in result["target"]["indexed_text"]["tags"]
    assert_suggestions_hold(conn, result, "fx-vpp-hongha")
    assert any("drop_tokens" in s["family"] for s in result["suggestions"])


def test_category_filter_is_reported_and_dropping_it_is_cheapest(conn):
    result = ask(conn, "fx-circle-k", q="circle k", radius_m=300, category="an_uong")

    assert codes(result) == ["CATEGORY"]
    assert_suggestions_hold(conn, result, "fx-circle-k")
    best = result["suggestions"][0]
    assert best["family"] == "category" and best["rank"] == 1
    assert best["penalty"] == pytest.approx((1 - CFG["whynot"]["lambda"]) * CFG["whynot"]["costs"]["category"])


def test_radius_is_reported_and_smallest_sufficient_radius_is_suggested(conn):
    result = ask(conn, "fx-pho-dakao", q="pho", radius_m=300)

    assert codes(result) == ["RADIUS"]
    assert result["reasons"][0]["distance_m"] > 800
    assert_suggestions_hold(conn, result, "fx-pho-dakao")
    best = result["suggestions"][0]
    assert best["family"] == "radius" and best["params"]["radius_m"] == 1000
    assert result["original_top_k"] == []
    assert best["retained"] is None


def test_several_blocking_filters_are_all_listed_and_still_answerable(conn):
    result = ask(conn, "fx-pho-dakao", q="circle", radius_m=300, category="tien_loi")

    assert codes(result) == ["TEXT", "CATEGORY", "RADIUS"]
    assert result["penalty"]["max_changes"] == 3
    assert_suggestions_hold(conn, result, "fx-pho-dakao")


def test_low_rank_prefers_increasing_k_when_it_keeps_the_original_results(conn):
    result = ask(conn, "fx-com-tam", k=2, radius_m=1000, sort="distance")

    assert codes(result) == ["RANK"]
    assert result["rank"] == 3 and result["reasons"][0]["rank"] == 3
    assert_suggestions_hold(conn, result, "fx-com-tam")
    best = result["suggestions"][0]
    assert best["family"] == "k" and best["params"]["k"] == 3
    assert best["delta_k"] == pytest.approx(1.0) and best["retained"] == 1.0


def test_poi_already_in_top_k_needs_no_suggestion(conn):
    result = ask(conn, "fx-circle-k", radius_m=1000)

    assert result["in_top_k"] is True
    assert codes(result) == ["IN_TOP_K"]
    assert result["suggestions"] == []


def test_alpha_suggestion_found_by_sweeping_crossings(conn):
    # "photocopy": tiệm photocopy khớp văn bản mạnh hơn nhưng xa hơn VPP Hồng Hà. Ở α = 0,6 tiệm
    # photocopy đứng đầu; giảm α (ưu tiên khoảng cách) thì Hồng Hà vượt lên.
    base = search(conn, params(q="photocopy", radius_m=2000, sort="combined"), CFG)
    assert [i["id"] for i in base["items"]][:2] == ["fx-photo-ngoclan", "fx-vpp-hongha"]

    result = ask(conn, "fx-vpp-hongha", k=1, q="photocopy", radius_m=2000, sort="combined")

    assert codes(result) == ["RANK"]
    assert_suggestions_hold(conn, result, "fx-vpp-hongha")
    alpha = [s for s in result["suggestions"] if s["family"] == "alpha"]
    assert alpha and alpha[0]["params"]["alpha"] < 0.6 and alpha[0]["rank"] == 1


def test_alpha_candidates_on_two_lines():
    items = [
        {"id": "m", "text_norm": 0.3, "geo_norm": 0.9},
        {"id": "a", "text_norm": 1.0, "geo_norm": 0.8},
    ]
    # Hai đường cắt nhau tại α = 0,125; bên trái giao điểm m đứng trên a.
    assert alpha_candidates(items, "m", 0.6) == [pytest.approx(0.124)]
    # Đã đứng đầu ở α0 thì không có α nào tốt hơn.
    assert alpha_candidates(items, "m", 0.1) == []


def test_point_inside_stays_strictly_inside_interval():
    assert point_inside(0.125, 0.0) == pytest.approx(0.124)
    assert point_inside(0.5, 1.0) == pytest.approx(0.501)
    tiny = point_inside(0.30001, 0.30002)
    assert 0.30001 < tiny < 0.30002


def test_strategy_membership():
    assert in_strategy({"k"}, "S1")
    assert in_strategy({"radius", "k"}, "S4") and not in_strategy({"radius", "category"}, "S4")
    assert in_strategy({"alpha", "sort"}, "S3")
    assert not in_strategy({"drop_tokens"}, "S7")


def test_eval_builds_questions_from_qrels_and_scores_strategies(conn):
    queries = [{"query_id": "T1", "query": "", "lat": REF["lat"], "lon": REF["lon"], "radius_m": 1000, "category": None}]
    qrels = [
        {"query_id": "T1", "poi_id": "fx-com-tam", "relevance": "1"},
        {"query_id": "T1", "poi_id": "fx-circle-k", "relevance": "1"},
        {"query_id": "T1", "poi_id": "fx-vpp-hongha", "relevance": "0"},
    ]
    questions = questions_from_qrels(conn, CFG, REF, queries, qrels, k=2)

    # Query rỗng: cả ba chế độ đều sắp theo khoảng cách; Cơm Tấm đứng hạng 3, Circle K hạng 1.
    assert [q["poi_id"] for q in questions] == ["fx-com-tam"] * 3
    out = run_question(conn, CFG, REF, questions[0], 2)
    assert out["row"]["reason"] == "RANK" and out["row"]["answered"] == 1
    by_name = {s["strategy"]: s for s in out["strategies"]}
    assert by_name["S1"]["answered"] == 1 and by_name["S1"]["answered_fixed_k"] == 0
    assert by_name["ALL"]["answered_fixed_k"] == 1  # thêm từ "com" đưa quán lên hạng 1 mà không tăng k
    summary = summarize_rows([run_question(conn, CFG, REF, q, 2)["row"] for q in questions])
    assert summary["valid"] == 3 and summary["answered"] == 1.0


def test_pipeline_steps_show_where_the_place_stops(conn):
    result = ask(conn, "fx-circle-k", q="circle k", radius_m=300, category="an_uong")

    assert [(s["code"], s["status"]) for s in result["steps"]] == [
        ("TEXT", "pass"),
        ("CATEGORY", "fail"),
        ("RADIUS", "pass"),
        ("RANK", "blocked"),
    ]
    browse = ask(conn, "fx-com-tam", k=2, radius_m=1000)
    assert [s["status"] for s in browse["steps"]] == ["skip", "skip", "pass", "fail"]


def test_reasons_and_changes_show_the_words_as_typed(conn):
    result = ask(conn, "fx-vpp-hongha", q="tài liệu", radius_m=1000)

    assert result["reasons"][0]["missing_words"] == ["tài", "liệu"]
    assert "“tài”" in result["reasons"][0]["short"]
    drop = next(s for s in result["suggestions"] if s["family"].startswith("drop_tokens"))
    assert "“tài”" in drop["changes"][0]["text"]


def test_added_words_come_only_from_the_place_name(conn):
    # Mô tả của tiệm có từ hiếm "tai", "lieu", "in"; đề xuất thêm từ chỉ được lấy từ tên tiệm.
    result = why_not(conn, params(q="circle", radius_m=2000), "fx-photo-ngoclan", CFG, return_all=True)
    added = {c["to"] for o in result["all_options"] for c in o["changes"] if c["dim"] == "add_token"}

    assert added and added <= {"tiem", "photocopy", "ngoc", "lan"}


def test_rebuilt_query_keeps_the_users_accents():
    assert rebuild_query("cà phê sữa", ("ca", "phe")) == "cà phê"
    assert rebuild_query("ăn sáng", ("an", "canteen"), "Canteen") == "ăn Canteen"
    # Khi không ghép lại được từ gốc (ví dụ đã sửa lỗi gõ) thì dùng token.
    assert rebuild_query("photocoppy", ("photocopy",)) == "photocopy"


def test_whynot_uses_the_corrected_query(conn):
    result = ask(conn, "fx-vpp-hongha", k=1, q="photocoppy", radius_m=2000, sort="combined")

    assert result["query"]["corrections"][0]["to"] == "photocopy"
    assert [r["code"] for r in result["reasons"]] == ["RANK"]
    assert_suggestions_hold(conn, result, "fx-vpp-hongha")


def test_unknown_poi_raises(conn):
    with pytest.raises(PoiNotFound):
        ask(conn, "khong-co", q="pho")


def test_search_alpha_parameter_changes_combined_order(conn):
    default = search(conn, params(q="photocopy", radius_m=2000, sort="combined"), CFG)
    geo_only = search(conn, params(q="photocopy", radius_m=2000, sort="combined", alpha=0), CFG)

    assert default["items"][0]["id"] == "fx-photo-ngoclan"
    assert geo_only["items"][0]["id"] == "fx-vpp-hongha"
    assert geo_only["meta"]["weights"]["combined"] == {"text": 0.0, "geo": 1.0}
    assert default["meta"]["alpha"] is None


@pytest.mark.parametrize("value, message", [("1.5", "alpha phải từ 0 đến 1"), ("x", "alpha phải là số"), ("nan", "hữu hạn")])
def test_invalid_alpha_is_rejected(value, message):
    from src.search import SearchError

    with pytest.raises(SearchError, match=message):
        params(alpha=value)
