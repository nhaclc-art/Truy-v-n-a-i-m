"""Tải Leaflet 1.9.4 vào static/vendor/leaflet/ (chạy một lần; các file tải về được commit).

leaflet.js và leaflet.css được kiểm SHA-256 theo mã SRI công bố tại leafletjs.com/download.html;
sai hash thì không ghi file nào.
"""
import base64
import hashlib
import sys

import requests

from scripts import use_utf8_stdio
from src.config import ROOT

VERSION = "1.9.4"
BASE_URL = f"https://cdn.jsdelivr.net/npm/leaflet@{VERSION}"
DEST = ROOT / "static" / "vendor" / "leaflet"
SRI = {
    "dist/leaflet.js": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
    "dist/leaflet.css": "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
}
FILES = {
    "dist/leaflet.js": "leaflet.js",
    "dist/leaflet.css": "leaflet.css",
    "dist/images/layers.png": "images/layers.png",
    "dist/images/layers-2x.png": "images/layers-2x.png",
    "dist/images/marker-icon.png": "images/marker-icon.png",
    "dist/images/marker-icon-2x.png": "images/marker-icon-2x.png",
    "dist/images/marker-shadow.png": "images/marker-shadow.png",
    "LICENSE": "LICENSE",
}


def sri_sha256(content: bytes) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")


def main() -> int:
    downloaded: dict[str, bytes] = {}
    for source, target in FILES.items():
        url = f"{BASE_URL}/{source}"
        try:
            resp = requests.get(url, timeout=30)
        except requests.RequestException as exc:
            print(f"Không tải được {url}: {exc}", file=sys.stderr)
            return 1
        if resp.status_code != 200:
            print(f"{url} trả HTTP {resp.status_code}", file=sys.stderr)
            return 1
        expected = SRI.get(source)
        if expected and sri_sha256(resp.content) != expected:
            print(f"Sai hash cho {source}; không ghi file nào.", file=sys.stderr)
            return 1
        downloaded[target] = resp.content

    for target, content in downloaded.items():
        path = DEST / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(f"Đã ghi Leaflet {VERSION} ({len(downloaded)} file) vào {DEST.relative_to(ROOT)}; hash JS/CSS khớp SRI.")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
