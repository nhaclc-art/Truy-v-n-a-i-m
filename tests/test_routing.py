from urllib.parse import parse_qs, urlparse

import pytest
import requests

from src.config import load_app_config
from src.routing import USER_AGENT, RoutingError, fetch_route, google_maps_url

ROUTING_CFG = load_app_config()["routing"]
FROM = (10.761357, 106.6821769)
TO = (10.7600, 106.6850)


class FakeResponse:
    def __init__(self, status_code, body=None, invalid_json=False):
        self.status_code = status_code
        self._body = body
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("not json")
        return self._body


class FakeHttp:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get(self, url, params, headers, timeout):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if self.exc:
            raise self.exc
        return self.response


OK_BODY = {
    "code": "Ok",
    "routes": [
        {
            "distance": 449.5,
            "duration": 363.7,
            "geometry": {"type": "LineString", "coordinates": [[106.682273, 10.76095], [106.6850, 10.7600]]},
        }
    ],
}


def route_with(http):
    return fetch_route(ROUTING_CFG, *FROM, *TO, http=http)


def test_success_converts_coordinates_to_lat_lon():
    http = FakeHttp(FakeResponse(200, OK_BODY))
    result = route_with(http)

    assert result == {"path": [[10.76095, 106.682273], [10.76, 106.685]], "distance_m": 449.5, "duration_s": 363.7}
    call = http.calls[0]
    # OSRM nhận lon,lat
    assert call["url"].endswith("/route/v1/driving/106.682177,10.761357;106.685000,10.760000")
    assert call["url"].startswith(ROUTING_CFG["base_url"])
    assert call["params"]["geometries"] == "geojson"
    assert call["headers"]["User-Agent"] == USER_AGENT
    assert call["timeout"] == ROUTING_CFG["timeout_s"]


@pytest.mark.parametrize(
    "http, status, code",
    [
        (FakeHttp(exc=requests.Timeout()), 504, "TIMEOUT"),
        (FakeHttp(exc=requests.ConnectionError()), 502, "UPSTREAM_UNREACHABLE"),
        (FakeHttp(FakeResponse(400, {"code": "NoRoute", "message": "Impossible route"})), 422, "NO_ROUTE"),
        (FakeHttp(FakeResponse(400, {"code": "NoSegment"})), 422, "NO_ROUTE"),
        (FakeHttp(FakeResponse(502, invalid_json=True)), 502, "BAD_RESPONSE"),
        (FakeHttp(FakeResponse(429, {"code": "TooBig"})), 502, "UPSTREAM_ERROR"),
        (FakeHttp(FakeResponse(200, {"code": "Ok", "routes": []})), 502, "BAD_RESPONSE"),
        (FakeHttp(FakeResponse(200, {"code": "Ok", "routes": [{"distance": 1, "duration": 1}]})), 502, "BAD_RESPONSE"),
    ],
)
def test_failures_map_to_meaningful_errors(http, status, code):
    with pytest.raises(RoutingError) as info:
        route_with(http)
    assert (info.value.status, info.value.code) == (status, code)


def test_google_maps_fallback_url():
    url = google_maps_url(*FROM, *TO)
    query = parse_qs(urlparse(url).query)

    assert url.startswith("https://www.google.com/maps/dir/?")
    assert query == {
        "api": ["1"],
        "origin": ["10.761357,106.682177"],
        "destination": ["10.760000,106.685000"],
        "travelmode": ["walking"],
    }
