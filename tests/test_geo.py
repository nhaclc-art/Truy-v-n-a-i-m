import math

import pytest

from src.geo import haversine_m, valid_lat_lon


def test_same_point_is_zero():
    assert haversine_m(10.761357, 106.6821769, 10.761357, 106.6821769) == 0


def test_distance_is_symmetric():
    forward = haversine_m(10.761357, 106.6821769, 10.7761576, 106.6903617)
    backward = haversine_m(10.7761576, 106.6903617, 10.761357, 106.6821769)
    assert forward == pytest.approx(backward)


def test_one_degree_of_latitude():
    # R * pi / 180 với R = 6 371 008,8 m
    assert haversine_m(0, 0, 1, 0) == pytest.approx(111_195.08, abs=0.1)


def test_campus_way_centre_to_campus_node():
    # Hai bản ghi OSM của cơ sở trong config/campus.json
    assert haversine_m(10.761357, 106.6821769, 10.7612196, 106.6822697) == pytest.approx(18.3, abs=0.5)


@pytest.mark.parametrize(
    "lat, lon, expected",
    [
        (10.76, 106.68, True),
        (-90, 180, True),
        (90.0001, 0, False),
        (0, -180.5, False),
        (math.nan, 0, False),
        (0, math.inf, False),
    ],
)
def test_valid_lat_lon(lat, lon, expected):
    assert valid_lat_lon(lat, lon) is expected
