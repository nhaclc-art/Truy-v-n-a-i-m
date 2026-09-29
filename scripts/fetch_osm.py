"""Tải một snapshot POI OpenStreetMap quanh cơ sở qua Overpass.

Chạy thủ công một lần khi thu dữ liệu, không dùng trong luồng tìm kiếm. Phản hồi thô được
lưu nguyên vẹn ở data/raw/, kèm file .meta.json ghi truy vấn, thời điểm và hash.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

import requests

from scripts import use_utf8_stdio
from src.config import ROOT, load_app_config, load_campus

# Instance công cộng theo wiki.openstreetmap.org/wiki/Overpass_API (đọc 18/09/2026).
OVERPASS_ENDPOINTS = {
    "main": "https://overpass-api.de/api/interpreter",
    "private-coffee": "https://overpass.private.coffee/api/interpreter",
    "vk-maps": "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
}
USER_AGENT = "georank-hcmue/0.1 (course demo; one-off OSM snapshot)"
RAW_DIR = ROOT / "data" / "raw"

# Tag khởi đầu theo docs/planning/04 §2, cộng trạm xăng, trạm xe buýt và chuỗi cửa hàng tiện lợi
# (có nơi gắn tag khác shop=convenience). Đây chỉ là bộ lọc thu nguồn; phân loại cuối cùng nằm ở
# bước dựng bản nháp corpus. Nhà trọ không lấy từ OSM vì không có tag chứng minh cho thuê.
CHAIN_PATTERN = "^(Circle K|Family ?Mart|GS ?25|Ministop|7-Eleven|B's Mart|WinMart)"
TAG_FILTERS = (
    '["amenity"~"^(restaurant|fast_food|cafe|food_court|fuel)$"]',
    '["shop"~"^(convenience|stationery|copyshop|books)$"]',
    '["highway"="bus_stop"]',
    f'["name"~"{CHAIN_PATTERN}",i]',
    f'["brand"~"{CHAIN_PATTERN}",i]',
)


def build_query(lat: float, lon: float, radius_m: int) -> str:
    around = f"(around:{radius_m},{lat},{lon})"
    parts = "\n".join(f"  nwr{tag_filter}{around};" for tag_filter in TAG_FILTERS)
    return f"[out:json][timeout:90];\n(\n{parts}\n);\nout center tags;\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Tải snapshot POI OSM quanh cơ sở qua Overpass.")
    parser.add_argument(
        "--endpoint",
        choices=OVERPASS_ENDPOINTS,
        default="main",
        help="instance Overpass; đổi khi instance chính quá tải (HTTP 429/504)",
    )
    args = parser.parse_args()
    endpoint = OVERPASS_ENDPOINTS[args.endpoint]

    point = load_campus()["reference_point"]
    radius_m = load_app_config()["dataset_scope_m"]
    query = build_query(point["lat"], point["lon"], radius_m)

    # Tên file theo giờ UTC nên mỗi lần tải là một snapshot mới, không ghi đè bản cũ.
    now = datetime.now(timezone.utc)
    raw_path = RAW_DIR / f"osm_{now:%Y%m%dT%H%M%SZ}.json"
    meta_path = raw_path.with_suffix(".meta.json")

    try:
        resp = requests.post(
            endpoint, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=120
        )
    except requests.RequestException as exc:
        print(f"Không kết nối được Overpass ({endpoint}): {exc}", file=sys.stderr)
        return 1
    if resp.status_code != 200:
        print(
            f"Overpass ({args.endpoint}) trả HTTP {resp.status_code}. Đợi vài phút rồi chạy lại "
            "hoặc thử --endpoint khác; không chạy lặp liên tục.",
            file=sys.stderr,
        )
        return 1
    try:
        payload = resp.json()
    except ValueError:
        print("Overpass trả nội dung không phải JSON; không lưu snapshot.", file=sys.stderr)
        return 1
    # Overpass có thể trả 200 kèm remark khi hết giờ/hết bộ nhớ; kết quả khi đó bị thiếu.
    if payload.get("remark"):
        print(f"Overpass báo lỗi, không lưu snapshot: {payload['remark']}", file=sys.stderr)
        return 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(resp.content)
    meta = {
        "endpoint": endpoint,
        "query": query,
        "retrieved_at": now.isoformat(timespec="seconds"),
        "osm_base_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
        "element_count": len(payload.get("elements", [])),
        "sha256": hashlib.sha256(resp.content).hexdigest(),
        "license": "ODbL 1.0, © OpenStreetMap contributors",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Đã lưu {raw_path.relative_to(ROOT)}: {meta['element_count']} phần tử, "
        f"dữ liệu OSM tới {meta['osm_base_timestamp']}"
    )
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
