import pytest

from app import create_app
from src import db
from src.config import load_app_config, load_campus
from src.ocr_query import build_ocr_query, fix_confusions
from src.search import SearchError, fts_expression, parse_params, search

CFG = load_app_config()
REF = load_campus()["reference_point"]
SIGN = "CIRCLE K\nCỬA HÀNG TIỆN LỢI 24/7\nĐT: 0909 123 456\nwww.circlek.com.vn"


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def run(conn, **args):
    return search(conn, parse_params({k: str(v) for k, v in args.items()}, CFG, REF), CFG)


def test_fts_expression_joins_with_and_or_or():
    assert fts_expression(["circle", "k"]) == '"circle" "k"'
    assert fts_expression(["circle", "k", "circle"], "any") == '"circle" OR "k"'


def test_match_any_returns_places_matching_some_words(conn):
    assert run(conn, q="circle pho", radius_m=2000)["items"] == []
    result = run(conn, q="circle pho", radius_m=2000, match="any")
    assert {i["id"] for i in result["items"]} == {"fx-circle-k", "fx-pho-dakao"}
    assert result["meta"]["match"] == "any" and " OR " in result["meta"]["fts_match"]


def test_invalid_match_is_rejected():
    with pytest.raises(SearchError, match="match"):
        parse_params({"match": "some"}, CFG, REF)


def test_ocr_confusions_are_fixed_only_into_known_words():
    tokens, fixes = fix_confusions(["c1rcle", "gs25", "x9y"], {"circle": 1, "gs25": 1})
    assert tokens == ["circle", "gs25", "x9y"]
    assert fixes == [{"from": "c1rcle", "to": "circle", "kind": "ocr"}]


def test_sign_text_becomes_a_clean_query(conn):
    built = build_ocr_query(conn, SIGN, CFG)
    kept = [k["token"] for k in built["kept"]]
    reasons = {d["token"]: d["reason"] for d in built["dropped"]}

    assert kept[:2] == ["circle", "k"] and {"cua", "hang", "tien", "loi"} <= set(kept)
    assert reasons["0909"].startswith("số") and reasons["www"] == "không có trong dữ liệu"
    assert run(conn, q=built["query"], radius_m=2000, match="any", sort="bm25")["items"][0]["id"] == "fx-circle-k"


def test_too_common_words_are_dropped(conn):
    # Trong 6 POI tổng hợp, "van phong pham" có ở 2 POI (≤ 50%): giữ; ngưỡng 0 thì bỏ hết.
    strict = {**CFG, "ocr": {**CFG["ocr"], "max_df_ratio": 0.0}}
    assert build_ocr_query(conn, "van phong pham", strict)["query"] == ""
    assert build_ocr_query(conn, "van phong pham", CFG)["query"] == "van phong pham"


def test_query_keeps_only_the_rarest_words(conn):
    small = {**CFG, "ocr": {**CFG["ocr"], "max_query_tokens": 2}}
    built = build_ocr_query(conn, "van phong pham circle", small)
    assert len(built["kept"]) == 2 and "circle" in built["query"]


def test_ocr_query_api(fixture_db):
    client = create_app(fixture_db).test_client()
    body = client.get("/api/ocr-query", query_string={"text": SIGN}).get_json()

    assert body["query"].startswith("circle k")
    assert client.get("/api/ocr-query", query_string={"text": " "}).status_code == 400
    assert client.get("/api/ocr-query", query_string={"text": "x" * 2001}).status_code == 400


def test_csp_allows_webassembly_but_not_eval(fixture_db):
    csp = create_app(fixture_db).test_client().get("/").headers["Content-Security-Policy"]
    assert "'wasm-unsafe-eval'" in csp and "'unsafe-eval'" not in csp.replace("'wasm-unsafe-eval'", "")
    assert "blob:" in csp
