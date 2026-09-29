"""Tạo/cập nhật bảng duyệt dữ liệu data/review_sheet.csv từ data/pois.csv.

Người kiểm tra mở link nguồn/bản đồ rồi điền các cột từ ket_qua trở đi. Chạy lại sau khi corpus đổi
sẽ giữ nguyên phần đã điền theo id. Bảng này không được import trực tiếp; `scripts.apply_review`
áp nó lên bản nháp để tạo data/pois.csv.
"""
import argparse
import csv
import sys
from pathlib import Path
from urllib.parse import urlencode

from scripts import use_utf8_stdio
from src.config import ROOT

INFO_FIELDS = (
    "id",
    "name",
    "category",
    "address",
    "verification_status",
    "verification_note",
    "source_url",
    "osm_map",
    "google_maps",
)
# toa_do_dung để cuối để bảng cũ (chưa có cột này) vẫn đọc được.
FILL_FIELDS = (
    "ket_qua",
    "ten_dung",
    "dia_chi_dung",
    "danh_muc_dung",
    "ghi_chu",
    "nguoi_kiem_tra",
    "ngay_kiem_tra",
    "toa_do_dung",
)


def map_links(lat: str, lon: str) -> tuple[str, str]:
    osm = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}"
    google = "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": f"{lat},{lon}"})
    return osm, google


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo/cập nhật data/review_sheet.csv để duyệt POI.")
    parser.add_argument("--pois", type=Path, default=ROOT / "data" / "pois.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "review_sheet.csv")
    args = parser.parse_args()

    with open(args.pois, encoding="utf-8-sig", newline="") as f:
        pois = list(csv.DictReader(f))
    filled = {}
    if args.out.exists():
        with open(args.out, encoding="utf-8-sig", newline="") as f:
            filled = {row["id"]: row for row in csv.DictReader(f)}

    rows = []
    for poi in sorted(pois, key=lambda p: (p["category"], p["name"], p["id"])):
        osm, google = map_links(poi["lat"], poi["lon"])
        row = {k: poi.get(k, "") for k in INFO_FIELDS[:7]}
        row.update(osm_map=osm, google_maps=google)
        previous = filled.get(poi["id"], {})
        row.update({k: previous.get(k) or "" for k in FILL_FIELDS})
        rows.append(row)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INFO_FIELDS + FILL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    done = sum(1 for r in rows if r["ket_qua"])
    removed = sorted(set(filled) - {p["id"] for p in pois})
    print(f"Đã ghi {args.out}: {len(rows)} POI, {done} đã có kết quả duyệt.")
    if removed:
        print(f"Bỏ khỏi bảng vì không còn trong pois.csv: {', '.join(removed)}")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
