import pytest

from app import create_app
from src import db, routing
from src.importer import import_csv


@pytest.fixture
def client(fixture_db):
    return create_app(fixture_db).test_client()


def test_health_reports_poi_count_and_version(client):
    body = client.get("/api/health").get_json()

    assert body["poi_count"] == 6
    assert body["dataset_version"].startswith("ds-")


def test_config_exposes_campus_but_not_routing_backend(client):
    body = client.get("/api/config").get_json()

    assert body["campus"]["reference_point"]["lat"] == pytest.approx(10.761357)
    assert [c["id"] for c in body["categories"]] == [
        "an_uong",
        "tien_loi",
        "vpp_photocopy",
        "nha_tro",
        "tram_xang",
        "tram_xe_buyt",
    ]
    assert "base_url" not in body["routing"]


def test_search_returns_items_and_metadata(client):
    body = client.get("/api/search", query_string={"q": "phở", "radius_m": 1000}).get_json()

    assert [i["id"] for i in body["items"]] == ["fx-pho-dakao"]
    assert body["meta"]["query_normalized"] == "pho"
    assert body["meta"]["dataset_version"].startswith("ds-")


def test_invalid_parameters_return_400_json(client):
    resp = client.get("/api/search", query_string={"radius_m": 123})

    assert resp.status_code == 400
    assert "radius_m" in resp.get_json()["error"]


def test_markup_in_query_is_returned_as_json_data(client):
    resp = client.get("/api/search", query_string={"q": "<script>alert(1)</script>"})

    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json()["meta"]["query"] == "<script>alert(1)</script>"


def test_poi_detail_and_not_found(client):
    detail = client.get("/api/pois/fx-nha-tro")
    missing = client.get("/api/pois/khong-co")

    assert detail.status_code == 200
    assert detail.get_json()["listing_url"] == "https://example.org/fixture/listing"
    assert detail.get_json()["category_label"] == "Nhà trọ"
    assert missing.status_code == 404 and "error" in missing.get_json()


def test_poi_list_for_whynot_picker(client):
    items = client.get("/api/pois").get_json()["items"]

    assert len(items) == 6
    assert {"id", "name", "category", "category_label", "lat", "lon"} <= items[0].keys()


def test_whynot_explains_and_suggests(client):
    body = client.get(
        "/api/whynot", query_string={"q": "circle k", "radius_m": 300, "category": "an_uong", "poi_id": "fx-circle-k"}
    ).get_json()

    assert body["target"]["name"] == "Circle K"
    assert [r["code"] for r in body["reasons"]] == ["CATEGORY"]
    assert body["suggestions"][0]["params"]["category"] is None
    assert body["query"]["k"] == 5


@pytest.mark.parametrize(
    "query, status",
    [
        ({"q": "pho"}, 400),
        ({"q": "pho", "poi_id": "khong-co"}, 404),
        ({"q": "pho", "poi_id": "fx-pho-dakao", "k": "0"}, 400),
        ({"q": "pho", "poi_id": "fx-pho-dakao", "k": "x"}, 400),
        ({"q": "pho", "poi_id": "fx-pho-dakao", "radius_m": 123}, 400),
    ],
)
def test_whynot_rejects_bad_requests(client, query, status):
    resp = client.get("/api/whynot", query_string=query)

    assert resp.status_code == status
    assert "error" in resp.get_json()


def test_itinerary_plans_a_route_across_legs(client):
    body = client.get(
        "/api/itinerary", query_string=[("stop", "hong ha"), ("stop", "com"), ("max_distance_m", "100000")]
    ).get_json()

    assert [s["id"] for s in body["routes"][0]["stops"]] == ["fx-vpp-hongha", "fx-com-tam"]
    assert body["legs"][0]["empty"] is False
    assert "total_distance_m" in body["routes"][0]


def test_itinerary_rejects_bad_requests(client):
    resp = client.get("/api/itinerary", query_string=[("stop", "only one")])

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_unknown_api_route_is_json_404(client):
    resp = client.get("/api/khong-co")

    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_index_is_served_with_security_headers(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert "script-src 'self'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_import_is_visible_on_the_next_request(client, fixture_db, fixture_rows, write_csv):
    query = {"q": "trà sữa", "radius_m": 2000}
    before = client.get("/api/search", query_string=query).get_json()
    assert before["items"] == []

    new_row = dict(fixture_rows[0], id="fx-tra-sua", name="Trà Sữa Mới", category="an_uong", tags="trà sữa")
    conn = db.connect(fixture_db)
    try:
        assert import_csv(conn, write_csv(fixture_rows + [new_row])).errors == []
    finally:
        conn.close()

    after = client.get("/api/search", query_string=query).get_json()
    assert [i["id"] for i in after["items"]] == ["fx-tra-sua"]
    assert after["meta"]["dataset_version"] != before["meta"]["dataset_version"]


@pytest.fixture
def fake_routing(monkeypatch):
    calls = []

    def fake_fetch(cfg, from_lat, from_lon, to_lat, to_lon):
        calls.append((from_lat, from_lon, to_lat, to_lon))
        return {"path": [[from_lat, from_lon], [to_lat, to_lon]], "distance_m": 250.0, "duration_s": 200.0}

    monkeypatch.setattr(routing, "wait_for_slot", lambda: None)
    monkeypatch.setattr(routing, "fetch_route", fake_fetch)
    return calls


ROUTE_QUERY = {"from_lat": 10.761357, "from_lon": 106.6821769, "poi_id": "fx-circle-k"}


def test_route_returns_path_distances_and_fallback(client, fake_routing):
    body = client.get("/api/route", query_string=ROUTE_QUERY).get_json()

    assert body["route"]["distance_m"] == 250.0
    assert body["poi"]["id"] == "fx-circle-k"
    assert body["straight_distance_m"] == pytest.approx(111.2, abs=0.5)
    assert body["mode_label"] == "đi bộ"
    assert "travelmode=walking" in body["google_maps_url"]
    assert fake_routing == [(10.761357, 106.6821769, 10.760357, 106.6821769)]


def test_route_upstream_failure_keeps_fallback_link(client, monkeypatch):
    def failing_fetch(*_args):
        raise routing.RoutingError(504, "TIMEOUT", "Máy chủ chỉ đường không phản hồi kịp")

    monkeypatch.setattr(routing, "wait_for_slot", lambda: None)
    monkeypatch.setattr(routing, "fetch_route", failing_fetch)
    resp = client.get("/api/route", query_string=ROUTE_QUERY)
    body = resp.get_json()

    assert resp.status_code == 504
    assert body["code"] == "TIMEOUT"
    assert "route" not in body
    assert body["google_maps_url"].startswith("https://www.google.com/maps/dir/?")


@pytest.mark.parametrize(
    "query, status",
    [
        ({"from_lat": "abc", "from_lon": 106.68, "poi_id": "fx-circle-k"}, 400),
        ({"from_lat": 95, "from_lon": 106.68, "poi_id": "fx-circle-k"}, 400),
        ({"from_lat": 10.76, "from_lon": 106.68}, 400),
        ({"from_lat": 10.76, "from_lon": 106.68, "poi_id": "khong-co"}, 404),
        ({"from_lat": 10.9, "from_lon": 106.68, "poi_id": "fx-circle-k"}, 400),
    ],
)
def test_route_rejects_bad_requests_without_calling_provider(client, fake_routing, query, status):
    resp = client.get("/api/route", query_string=query)

    assert resp.status_code == status
    assert "error" in resp.get_json()
    assert fake_routing == []


def test_missing_database_returns_503(tmp_path):
    client = create_app(tmp_path / "empty.db").test_client()
    resp = client.get("/api/search")

    assert resp.status_code == 503
    assert "import_pois" in resp.get_json()["error"]
