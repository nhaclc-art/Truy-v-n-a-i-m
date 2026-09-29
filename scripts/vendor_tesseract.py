"""Tải bộ đọc chữ Tesseract.js 5.1.1 vào static/vendor/tesseract/ để đọc biển hiệu ngay trong trình duyệt.

Chạy một lần sau khi clone (các file này không commit vì nặng khoảng 12 MB):
    python -m scripts.vendor_tesseract

Gồm: tesseract.min.js và worker.min.js (tesseract.js 5.1.1), lõi WebAssembly chỉ LSTM có và không có
SIMD (tesseract.js-core 5.1.1), dữ liệu nhận dạng tiếng Việt và tiếng Anh loại best_int
(@tesseract.js-data 1.0.0, 4.0.0_best_int). Phiên bản trên jsDelivr/npm là cố định.

Kiểm tra toàn vẹn: lần tải đầu ghi SHA-256 từng file vào config/vendor_tesseract.lock.json (commit file
này); các lần sau phải khớp, sai một file thì không ghi file nào. Các gói đều theo giấy phép Apache-2.0.
"""
import hashlib
import json
import sys

import requests

from scripts import use_utf8_stdio
from src.config import CONFIG_DIR, ROOT

DEST = ROOT / "static" / "vendor" / "tesseract"
LOCK = CONFIG_DIR / "vendor_tesseract.lock.json"
CDN = "https://cdn.jsdelivr.net/npm"
FILES = {
    f"{CDN}/tesseract.js@5.1.1/dist/tesseract.min.js": "tesseract.min.js",
    f"{CDN}/tesseract.js@5.1.1/dist/worker.min.js": "worker.min.js",
    f"{CDN}/tesseract.js@5.1.1/LICENSE.md": "LICENSE-tesseract.js.md",
    f"{CDN}/tesseract.js-core@5.1.1/tesseract-core-simd-lstm.wasm.js": "core/tesseract-core-simd-lstm.wasm.js",
    f"{CDN}/tesseract.js-core@5.1.1/tesseract-core-lstm.wasm.js": "core/tesseract-core-lstm.wasm.js",
    f"{CDN}/tesseract.js-core@5.1.1/LICENSE": "LICENSE-tesseract.js-core",
    f"{CDN}/@tesseract.js-data/vie@1.0.0/4.0.0_best_int/vie.traineddata.gz": "lang/vie.traineddata.gz",
    f"{CDN}/@tesseract.js-data/eng@1.0.0/4.0.0_best_int/eng.traineddata.gz": "lang/eng.traineddata.gz",
}


def main() -> int:
    locked = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    downloaded: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for url, target in FILES.items():
        print(f"Tải {target}…")
        try:
            resp = requests.get(url, timeout=120)
        except requests.RequestException as exc:
            print(f"Không tải được {url}: {exc}", file=sys.stderr)
            return 1
        if resp.status_code != 200:
            print(f"{url} trả HTTP {resp.status_code}", file=sys.stderr)
            return 1
        digest = hashlib.sha256(resp.content).hexdigest()
        if target in locked and locked[target] != digest:
            print(f"Sai SHA-256 cho {target} so với {LOCK.name}; không ghi file nào.", file=sys.stderr)
            return 1
        downloaded[target] = resp.content
        hashes[target] = digest

    for target, content in downloaded.items():
        path = DEST / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if not locked:
        LOCK.write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Lần tải đầu: đã ghi SHA-256 vào {LOCK.relative_to(ROOT)} (nên commit file này).")
    total = sum(len(c) for c in downloaded.values()) / 1_000_000
    print(f"Đã ghi {len(downloaded)} file ({total:.1f} MB) vào {DEST.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
