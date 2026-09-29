from src.config import load_app_config, load_campus


def test_campus_reference_point_is_in_ho_chi_minh_city():
    point = load_campus()["reference_point"]
    # Hộp bao rộng quanh TP.HCM, chỉ để bắt lỗi đảo lat/lon hoặc gõ nhầm tọa độ.
    assert 10.3 < point["lat"] < 11.2
    assert 106.3 < point["lon"] < 107.1


def test_app_config_is_consistent():
    cfg = load_app_config()
    search = cfg["search"]
    assert max(search["allowed_radii_m"]) <= cfg["dataset_scope_m"]
    assert 0 < search["default_limit"] <= search["max_limit"]

    ids = [c["id"] for c in cfg["categories"]]
    assert len(ids) == len(set(ids))

    assert cfg["geofence"]["exit_m"] > cfg["geofence"]["enter_m"]

    weights = cfg["ranking"]["combined_weights"]
    assert abs(weights["text"] + weights["geo"] - 1) < 1e-9

    itinerary = cfg["itinerary"]
    assert itinerary["search_radius_m"] in search["allowed_radii_m"]
    assert itinerary["default_max_distance_m"] in itinerary["allowed_max_distance_m"]
    assert itinerary["min_legs"] <= len(itinerary["default_legs_hint"]) <= itinerary["max_legs"]
