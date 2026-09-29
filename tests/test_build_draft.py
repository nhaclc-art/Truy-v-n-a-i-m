from scripts.build_draft import collect_candidates, dedupe, match_rule, select, to_row
from src.config import load_osm_corpus_rules

CENTER = (10.761357, 106.6821769)
RADII = [300, 500, 1000, 2000]
RULES = load_osm_corpus_rules()


def node(osm_id, dlat, tags, dlon=0.0):
    return {"type": "node", "id": osm_id, "lat": CENTER[0] + dlat, "lon": CENTER[1] + dlon, "tags": tags}


# 0,001 độ vĩ ≈ 111 m
ELEMENTS = [
    node(1, 0.0010, {"amenity": "restaurant", "name": "Cơm Tấm A", "cuisine": "rice;vietnamese"}),
    node(2, 0.0010, {"amenity": "restaurant"}),
    node(3, 0.0020, {"shop": "books", "name": "Nhà Sách B"}),
    node(4, 0.0020, {"shop": "books", "name": "Nhà Sách Văn Phòng Phẩm C"}),
    node(5, 0.0010, {"amenity": "cafe", "name": "Cà Phê D"}, dlon=0.0010),
    {
        "type": "way",
        "id": 6,
        "center": {"lat": CENTER[0] + 0.0011, "lon": CENTER[1] + 0.0010},
        "tags": {"amenity": "cafe", "name": "Cà phê D"},
    },
    node(7, 0.0300, {"amenity": "restaurant", "name": "Quán Xa"}),
    node(8, 0.0012, {"amenity": "restaurant", "name": "Bún E", "cuisine": "noodle", "addr:street": "An Dương Vương"}),
    node(9, 0.0013, {"amenity": "fast_food", "name": "Bánh Mì F"}),
    node(10, 0.0050, {"amenity": "restaurant", "name": "Quán G"}),
    node(11, 0.0040, {"amenity": "cafe"}),
    node(12, 0.0005, {"highway": "bus_stop", "name": "Đại học Sư phạm", "route_ref": "1;14; 56"}),
    node(13, 0.0020, {"amenity": "fuel", "brand": "Petrolimex"}),
    node(14, -0.0005, {"shop": "supermarket", "name": "Circle K"}),
    node(15, 0.0010, {"amenity": "restaurant"}, dlon=0.0001),
]


def collect():
    return collect_candidates(ELEMENTS, RULES["rules"], CENTER, RADII, 2000, unnamed_within_m=300)


def test_rules_for_books_and_convenience_chains():
    rules = RULES["rules"]
    assert match_rule({"shop": "books", "name": "Nhà Sách B"}, rules) is None
    assert match_rule({"shop": "books", "name": "Nhà Sách VPP C"}, rules)["category"] == "vpp_photocopy"
    assert match_rule({"shop": "supermarket", "name": "Circle K"}, rules)["category"] == "tien_loi"
    assert match_rule({"shop": "kiosk", "brand": "FamilyMart"}, rules)["category"] == "tien_loi"
    assert match_rule({"amenity": "fuel"}, rules)["category"] == "tram_xang"
    assert match_rule({"highway": "bus_stop"}, rules)["category"] == "tram_xe_buyt"
    assert match_rule({"shop": "supermarket", "name": "Co.opmart"}, rules) is None


def test_collect_keeps_near_unnamed_places_and_skips_far_ones():
    candidates, stats = collect()
    by_id = {c.osm_id: c for c in candidates}

    assert set(by_id) == {1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14, 15}
    assert stats == {"không có tên": 1, "không khớp luật": 1, "ngoài phạm vi": 1}
    assert (by_id[2].name, by_id[2].name_source) == ("Quán ăn (chưa rõ tên)", "unnamed")
    assert (by_id[13].name, by_id[13].name_source) == ("Petrolimex", "brand")
    assert by_id[1].ring_m == 300 and by_id[10].ring_m == 1000


def test_dedupe_merges_named_duplicates_but_not_unnamed_neighbours():
    candidates, _ = collect()
    kept, removed = dedupe(candidates, 30)
    kept_ids = {c.osm_id for c in kept}

    assert removed == 1
    assert 5 in kept_ids and 6 not in kept_ids
    assert {2, 15} <= kept_ids  # hai quán không tên cách nhau ~11 m vẫn là hai bản ghi


def test_select_applies_quota_per_ring_and_prefers_richer_records():
    candidates, _ = collect()
    food = [c for c in dedupe(candidates, 30)[0] if c.rule["category"] == "an_uong"]
    quotas = {"an_uong": {"300": 2, "500": None, "1000": None, "2000": None}}
    selected = select(food, quotas)

    assert [c.osm_id for c in selected if c.ring_m == 300] == [8, 1]
    assert 10 in {c.osm_id for c in selected}


def test_to_row_keeps_provenance_and_explains_generated_names():
    candidates, _ = collect()
    by_id = {c.osm_id: c for c in candidates}
    cuisine = RULES["cuisine_vi"]

    row = to_row(by_id[1], "2026-09-18", cuisine)
    assert row["id"] == "osm-node-1"
    assert row["tags"] == "nhà hàng quán ăn; cơm; món Việt"
    assert row["source_url"] == "https://www.openstreetmap.org/node/1"
    assert (row["verification_status"], row["verification_note"]) == ("source_only", "")

    assert "tâm hình học" in to_row(by_id[6], "2026-09-18", cuisine)["verification_note"]
    assert to_row(by_id[8], "2026-09-18", cuisine)["address"] == "An Dương Vương"
    assert "cần người kiểm tra điền tên thật" in to_row(by_id[2], "2026-09-18", cuisine)["verification_note"]
    assert "tag brand" in to_row(by_id[13], "2026-09-18", cuisine)["verification_note"]
    assert to_row(by_id[12], "2026-09-18", cuisine)["tags"] == "trạm xe buýt; điểm dừng xe buýt; tuyến 1, 14, 56"
