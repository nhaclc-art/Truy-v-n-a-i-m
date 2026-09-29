"""Chỉ đường đi bộ qua OSRM của FOSSGIS (routing.openstreetmap.de) và liên kết Google Maps dự phòng.

Backend chỉ gọi tới base_url cố định trong config; client không truyền URL. OSRM nhận tọa độ theo
thứ tự lon,lat; đường đi trả cho Leaflet được đổi về lat,lon. Phương tiện do instance quyết định
(routed-foot = đi bộ), chuỗi profile trong URL bị OSRM bỏ qua.
"""
import math
import threading
import time
from urllib.parse import urlencode

import requests

USER_AGENT = "GeoRank-HCMUE/0.1 (university course demo; walking directions on user request)"
# Điều khoản FOSSGIS: tối đa 1 request/giây.
MIN_INTERVAL_S = 1.0

_slot_lock = threading.Lock()
_next_slot = 0.0


class RoutingError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def wait_for_slot() -> None:
    """Giãn các request tới máy chủ chỉ đường tối thiểu MIN_INTERVAL_S giây."""
    global _next_slot
    with _slot_lock:
        now = time.monotonic()
        wait = _next_slot - now
        _next_slot = max(now, _next_slot) + MIN_INTERVAL_S
    if wait > 0:
        time.sleep(wait)


def google_maps_url(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> str:
    query = urlencode(
        {
            "api": "1",
            "origin": f"{from_lat:.6f},{from_lon:.6f}",
            "destination": f"{to_lat:.6f},{to_lon:.6f}",
            "travelmode": "walking",
        }
    )
    return f"https://www.google.com/maps/dir/?{query}"


def fetch_route(routing_cfg: dict, from_lat: float, from_lon: float, to_lat: float, to_lon: float, http=requests) -> dict:
    url = (
        f"{routing_cfg['base_url']}/route/v1/driving/"
        f"{from_lon:.6f},{from_lat:.6f};{to_lon:.6f},{to_lat:.6f}"
    )
    params = {"overview": "full", "geometries": "geojson", "alternatives": "false", "steps": "false"}
    try:
        resp = http.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=routing_cfg["timeout_s"])
    except requests.Timeout:
        raise RoutingError(504, "TIMEOUT", "Máy chủ chỉ đường không phản hồi kịp") from None
    except requests.RequestException:
        raise RoutingError(502, "UPSTREAM_UNREACHABLE", "Không kết nối được máy chủ chỉ đường") from None

    try:
        body = resp.json()
    except ValueError:
        raise RoutingError(502, "BAD_RESPONSE", "Máy chủ chỉ đường trả dữ liệu không hợp lệ") from None
    code = body.get("code") if isinstance(body, dict) else None
    if code in ("NoRoute", "NoSegment"):
        raise RoutingError(422, "NO_ROUTE", "Không tìm được tuyến đi bộ giữa hai điểm")
    if resp.status_code != 200 or code != "Ok":
        raise RoutingError(502, "UPSTREAM_ERROR", f"Máy chủ chỉ đường báo lỗi ({code or resp.status_code})")

    try:
        route = body["routes"][0]
        distance = float(route["distance"])
        duration = float(route["duration"])
        path = [[float(lat), float(lon)] for lon, lat in route["geometry"]["coordinates"]]
    except (KeyError, IndexError, TypeError, ValueError):
        raise RoutingError(502, "BAD_RESPONSE", "Máy chủ chỉ đường trả dữ liệu không hợp lệ") from None
    if len(path) < 2 or not (math.isfinite(distance) and math.isfinite(duration)):
        raise RoutingError(502, "BAD_RESPONSE", "Máy chủ chỉ đường trả dữ liệu không hợp lệ")
    return {"path": path, "distance_m": distance, "duration_s": duration}
