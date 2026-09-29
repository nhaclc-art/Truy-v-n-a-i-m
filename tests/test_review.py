import pytest

from src.review import apply_review, parse_coords

POIS = [
    {"id": "a", "name": "Quán cà phê (chưa rõ tên)", "category": "an_uong", "address": "", "lat": "10.76", "lon": "106.68",
     "verification_status": "source_only", "verified_at": "", "verification_note": "OSM không có tên."},
    {"id": "b", "name": "Nhà hàng B", "category": "an_uong", "address": "", "lat": "10.761", "lon": "106.681",
     "verification_status": "source_only", "verified_at": "", "verification_note": ""},
    {"id": "c", "name": "Quán C", "category": "an_uong", "address": "", "lat": "10.762", "lon": "106.682",
     "verification_status": "source_only", "verified_at": "", "verification_note": ""},
    {"id": "d", "name": "Quán D", "category": "an_uong", "address": "", "lat": "10.763", "lon": "106.683",
     "verification_status": "source_only", "verified_at": "", "verification_note": ""},
]


def review(poi_id, result, **extra):
    row = {"id": poi_id, "ket_qua": result, "nguoi_kiem_tra": "Người duyệt", "ngay_kiem_tra": "2026-09-18"}
    row.update(extra)
    return row


def test_results_map_to_verification_status_and_keep_provenance():
    reviews = [
        review("a", "dung_tai_cho", ten_dung="Cà Phê Thật", ghi_chu="đi tận nơi"),
        review("b", "sai", dia_chi_dung="12 Đường X", toa_do_dung="10.7659641, 106.6823741", ghi_chu="Foody"),
        review("c", "dong_cua", ghi_chu="đã đóng"),
        review("d", "khong_ro"),
        review("gone", "dung"),
    ]
    rows, errors, counts, stale = apply_review(POIS, reviews)
    by_id = {r["id"]: r for r in rows}

    assert errors == []
    assert by_id["a"]["name"] == "Cà Phê Thật"
    assert by_id["a"]["verification_status"] == "field_checked"
    assert by_id["a"]["verification_note"] == (
        "OSM không có tên. Duyệt 2026-09-18 (Người duyệt, kết quả: dung_tai_cho): đi tận nơi"
    )
    assert (by_id["b"]["address"], by_id["b"]["lat"], by_id["b"]["lon"]) == ("12 Đường X", "10.7659641", "106.6823741")
    assert by_id["b"]["verification_status"] == "cross_checked"
    assert by_id["c"]["verification_status"] == "uncertain"
    assert by_id["d"]["verification_status"] == "source_only"
    assert by_id["d"]["verification_note"] == "Duyệt 2026-09-18 (Người duyệt, kết quả: khong_ro)"
    assert counts == {"dung_tai_cho": 1, "sai": 1, "dong_cua": 1, "khong_ro": 1}
    assert stale == ["gone"]


def test_unreviewed_rows_are_unchanged():
    rows, errors, counts, _ = apply_review(POIS, [{"id": "a", "ket_qua": ""}])
    assert rows == POIS and errors == [] and not counts


@pytest.mark.parametrize(
    "bad, message",
    [
        (review("a", "ok"), "ket_qua 'ok' không hợp lệ"),
        (review("a", "dung", nguoi_kiem_tra=""), "cần nguoi_kiem_tra"),
        (review("a", "sai", toa_do_dung="10.76"), "toa_do_dung phải dạng"),
        (review("a", "sai", toa_do_dung="95, 106"), "ngoài miền"),
    ],
)
def test_invalid_review_rows_are_reported(bad, message):
    _, errors, _, _ = apply_review(POIS, [bad])
    assert any(message in e for e in errors), errors


def test_parse_coords_accepts_comma_or_space():
    assert parse_coords("10.76, 106.68") == (10.76, 106.68)
    assert parse_coords("10.76 106.68") == (10.76, 106.68)
