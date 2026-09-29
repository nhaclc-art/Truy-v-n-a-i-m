import unicodedata

import pytest

from src.normalize import analyze, normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Văn Phòng Phẩm", "van phong pham"),
        ("van phong pham", "van phong pham"),
        ("ĐƯỜNG Đinh Tiên Hoàng", "duong dinh tien hoang"),
        ('  Cơm-tấm   "Ba Ghiền"!! ', "com tam ba ghien"),
        ("Phở 24h", "pho 24h"),
        ("<b>Trà sữa</b>", "b tra sua b"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_nfc_and_nfd_input_normalize_the_same():
    text = "Nhà trọ hẻm Ươm Đỏ"
    assert normalize(unicodedata.normalize("NFD", text)) == normalize(unicodedata.normalize("NFC", text))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("VPP", ["van", "phong", "pham"]),
        ("tiệm photo", ["tiem", "photocopy"]),
        ("Café", ["ca", "phe"]),
        ("Highlands Coffee", ["highlands", "ca", "phe"]),
        ("phở bò", ["pho", "bo"]),
        ("trạm bus", ["tram", "xe", "buyt"]),
    ],
)
def test_analyze_expands_aliases(raw, expected):
    assert analyze(raw) == expected
