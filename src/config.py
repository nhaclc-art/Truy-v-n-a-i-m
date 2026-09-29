"""Đọc cấu hình JSON trong config/. Các file này không chứa secrets."""
import json
from pathlib import Path

from src.geo import valid_lat_lon

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_campus() -> dict:
    campus = _load("campus.json")
    lat, lon = campus["reference_point"]["lat"], campus["reference_point"]["lon"]
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and valid_lat_lon(lat, lon)):
        raise ValueError(f"config/campus.json: tọa độ tham chiếu không hợp lệ ({lat}, {lon})")
    return campus


def load_app_config() -> dict:
    cfg = _load("app.json")
    search = cfg["search"]
    if search["default_radius_m"] not in search["allowed_radii_m"]:
        raise ValueError("config/app.json: default_radius_m phải nằm trong allowed_radii_m")
    if search["default_sort"] not in search["sort_modes"]:
        raise ValueError("config/app.json: default_sort phải nằm trong sort_modes")
    itinerary = cfg["itinerary"]
    if itinerary["search_radius_m"] not in search["allowed_radii_m"]:
        raise ValueError("config/app.json: itinerary.search_radius_m phải nằm trong search.allowed_radii_m")
    if itinerary["default_max_distance_m"] not in itinerary["allowed_max_distance_m"]:
        raise ValueError("config/app.json: itinerary.default_max_distance_m phải nằm trong allowed_max_distance_m")
    if not itinerary["min_legs"] <= len(itinerary["default_legs_hint"]) <= itinerary["max_legs"]:
        raise ValueError("config/app.json: default_legs_hint phải có số chặng từ min_legs đến max_legs")
    return cfg


def load_aliases() -> dict[str, str]:
    return _load("aliases.json")["aliases"]


def load_osm_corpus_rules() -> dict:
    return _load("osm_corpus.json")
