import pytest

from scripts.benchmark import percentile


def test_percentile_interpolates_linearly():
    assert percentile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
    assert percentile([1, 2, 3, 4, 5], 0.95) == pytest.approx(4.8)
    assert percentile([10], 0.95) == 10
