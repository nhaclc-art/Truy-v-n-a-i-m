"""Dựng bản nháp corpus data/pois_draft.csv.

Nguồn: snapshot OSM mới nhất trong data/raw/, lọc theo luật cố định trong config/osm_corpus.json,
cộng các CSV nguồn thủ công trong data/manual/. Bản nháp cần người duyệt rồi mới chép thành
data/pois.csv để import; script không ghi vào data/pois.csv.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from scripts import use_utf8_stdio
from src.config import ROOT, load_app_config, load_campus, load_osm_corpus_rules
from src.geo import haversine_m
from src.importer import POI_FIELDS
from src.normalize import normalize

RAW_DIR = ROOT / "data" / "raw"
MANUAL_DIR = ROOT / "data" / "manual"
DRAFT_PATH = ROOT / "data" / "pois_draft.csv"

TYPE_ORDER = {"node": 0, "way": 1, "relation": 2}
# Bản ghi có nhiều thông tin kiểm chứng được hơn thì được ưu tiên trong cùng một vòng.
RICHNESS_TAGS = ("addr:street", "cuisine", "opening_hours")


@dataclass
class Candidate:
    osm_type: str
    osm_id: int
    tags: dict
    rule: dict
    name: str
    name_source: str  # "name", "brand" hoặc "unnamed"
    lat: float
    lon: float
    distance_m: float
    ring_m: int

    @property
    def sort_key(self) -> tuple:
        richness = sum(1 for t in RICHNESS_TAGS if self.tags.get(t))
        return (-richness, TYPE_ORDER[self.osm_type], self.osm_id)


def osm_name(tags: dict) -> tuple[str, str]:
    """Tên hiển thị lấy từ tag name, thiếu thì từ brand."""
    for key in ("name", "brand"):
        value = (tags.get(key) or "").strip()
        if value:
            return value, key
    return "", "unnamed"


def match_rule(tags: dict, rules: list[dict]) -> dict | None:
    name = normalize(osm_name(tags)[0])
    for rule in rules:
        pattern = rule.get("name_pattern")
        if "key" in rule:
            if tags.get(rule["key"]) != rule["value"]:
                continue
        elif not pattern:
            continue  # luật không có key phải có name_pattern, tránh khớp mọi phần tử
        if pattern and not re.search(pattern, name):
            continue
        return rule
    return None


def collect_candidates(elements, rules, center, radii, scope_m, unnamed_within_m=0) -> tuple[list[Candidate], Counter]:
    stats: Counter = Counter()
    candidates = []
    for el in elements:
        tags = el.get("tags", {})
        rule = match_rule(tags, rules)
        if rule is None:
            stats["không khớp luật"] += 1
            continue
        point = el if "lat" in el else el.get("center", {})
        if "lat" not in point:
            stats["không có tọa độ"] += 1
            continue
        distance = haversine_m(center[0], center[1], point["lat"], point["lon"])
        if distance > scope_m:
            stats["ngoài phạm vi"] += 1
            continue
        name, name_source = osm_name(tags)
        if not name:
            # POI không tên chỉ nhận khi rất gần trường, với nhãn tạm để người kiểm tra điền tên thật.
            if rule.get("unnamed_label") and distance <= unnamed_within_m:
                name = rule["unnamed_label"]
            else:
                stats["không có tên"] += 1
                continue
        ring = next((r for r in radii if distance <= r), scope_m)
        candidates.append(
            Candidate(el["type"], el["id"], tags, rule, name, name_source, point["lat"], point["lon"], distance, ring)
        )
    return candidates, stats


def dedupe(candidates: list[Candidate], max_distance_m: float) -> tuple[list[Candidate], int]:
    """Bỏ bản ghi trùng: cùng tên chuẩn hóa và cách nhau không quá max_distance_m.

    POI không tên không bị gộp vì nhãn tạm giống nhau không có nghĩa là cùng một chỗ.
    """
    kept_by_name: dict[str, list[Candidate]] = defaultdict(list)
    kept = []
    for c in sorted(candidates, key=lambda c: c.sort_key):
        if c.name_source != "unnamed":
            same_name = kept_by_name[normalize(c.name)]
            if any(haversine_m(k.lat, k.lon, c.lat, c.lon) <= max_distance_m for k in same_name):
                continue
            same_name.append(c)
        kept.append(c)
    return kept, len(candidates) - len(kept)


def select(candidates: list[Candidate], quotas: dict[str, dict[str, int | None]]) -> list[Candidate]:
    """Lấy tối đa quota POI cho mỗi (danh mục, vòng bán kính); quota null nghĩa là lấy hết."""
    groups: dict[tuple[str, int], list[Candidate]] = defaultdict(list)
    for c in candidates:
        groups[(c.rule["category"], c.ring_m)].append(c)
    selected = []
    for (category, ring), group in sorted(groups.items()):
        quota = quotas[category][str(ring)]
        group.sort(key=lambda c: c.sort_key)
        selected.extend(group if quota is None else group[:quota])
    return selected


def to_row(c: Candidate, retrieved_date: str, cuisine_vi: dict[str, str]) -> dict:
    t = c.tags
    name = c.name
    extra = [c.rule["tags_vi"]]
    for value in (t.get("cuisine") or "").split(";"):
        value = value.strip()
        if value:
            extra.append(cuisine_vi.get(value, value.replace("_", " ")))
    routes = [r.strip() for r in (t.get("route_ref") or "").split(";") if r.strip()]
    if routes:
        extra.append("tuyến " + ", ".join(routes))
    for key in ("alt_name", "name:en", "brand"):
        value = (t.get(key) or "").strip()
        if value and value != name and value not in extra:
            extra.append(value)
    address = ""
    if t.get("addr:street"):
        address = " ".join(p for p in (t.get("addr:housenumber"), t["addr:street"]) if p)
    notes = []
    if c.name_source == "brand":
        notes.append("Tên lấy từ tag brand vì OSM không có tag name.")
    elif c.name_source == "unnamed":
        notes.append("OSM không có tên; tên hiển thị là mô tả tạm, cần người kiểm tra điền tên thật.")
    if c.osm_type != "node":
        notes.append(f"Tọa độ là tâm hình học của {c.osm_type} (Overpass out center), không phải lối vào.")
    note = " ".join(notes)
    return {
        "id": f"osm-{c.osm_type}-{c.osm_id}",
        "name": name,
        "category": c.rule["category"],
        "address": address,
        "lat": f"{c.lat:.7f}",
        "lon": f"{c.lon:.7f}",
        "description": (t.get("description") or "").strip(),
        "tags": "; ".join(extra),
        "source_url": f"https://www.openstreetmap.org/{c.osm_type}/{c.osm_id}",
        "source_type": "osm",
        "source_id": f"{c.osm_type}/{c.osm_id}",
        "retrieved_at": retrieved_date,
        "verification_status": "source_only",
        "verified_at": "",
        "verification_note": note,
        "listing_url": "",
        "listing_checked_at": "",
        "opening_hours": (t.get("opening_hours") or "").strip(),
    }


def read_manual_rows() -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    for path in sorted(MANUAL_DIR.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames or []) != set(POI_FIELDS):
                errors.append(f"{path.name}: header phải đúng các cột của schema POI")
                continue
            rows.extend(reader)
    return rows, errors


def latest_snapshot() -> Path | None:
    snapshots = sorted(p for p in RAW_DIR.glob("osm_*.json") if not p.name.endswith(".meta.json"))
    return snapshots[-1] if snapshots else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Dựng data/pois_draft.csv từ snapshot OSM và data/manual/.")
    parser.add_argument("--snapshot", type=Path, help="mặc định: snapshot mới nhất trong data/raw/")
    args = parser.parse_args()

    snapshot = args.snapshot or latest_snapshot()
    if snapshot is None:
        print("Chưa có snapshot trong data/raw/; chạy python -m scripts.fetch_osm trước.", file=sys.stderr)
        return 1
    meta_path = snapshot.with_suffix(".meta.json")
    if not meta_path.exists():
        print(f"Thiếu {meta_path.name}; snapshot không rõ thời điểm lấy nên không dùng.", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    elements = json.loads(snapshot.read_text(encoding="utf-8"))["elements"]

    app = load_app_config()
    rules = load_osm_corpus_rules()
    point = load_campus()["reference_point"]
    radii = sorted(app["search"]["allowed_radii_m"])

    candidates, stats = collect_candidates(
        elements,
        rules["rules"],
        (point["lat"], point["lon"]),
        radii,
        app["dataset_scope_m"],
        rules["unnamed_within_m"],
    )
    candidates, duplicates = dedupe(candidates, rules["dedupe_distance_m"])
    selected = select(candidates, rules["per_ring_quota"])
    rows = [
        to_row(c, meta["retrieved_at"][:10], rules["cuisine_vi"])
        for c in sorted(selected, key=lambda c: (c.rule["category"], c.distance_m, c.osm_id))
    ]

    manual_rows, errors = read_manual_rows()
    clashes = {r["id"] for r in rows} & {r["id"] for r in manual_rows}
    errors += [f"id '{i}' vừa có trong OSM vừa có trong data/manual/" for i in sorted(clashes)]
    if errors:
        for message in errors:
            print(f"LỖI: {message}", file=sys.stderr)
        return 1
    rows += manual_rows

    with open(DRAFT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POI_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Snapshot {snapshot.name}: {len(elements)} phần tử, lấy lúc {meta['retrieved_at']}")
    print("Loại: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())) + f", trùng {duplicates}")
    pool = Counter((c.rule["category"], c.ring_m) for c in candidates)
    chosen = Counter((c.rule["category"], c.ring_m) for c in selected)
    print("Chọn/ứng viên theo vòng: " + "  ".join(f"≤{r} m" for r in radii))
    for category in sorted({c.rule["category"] for c in candidates}):
        cells = "  ".join(f"{chosen[(category, r)]}/{pool[(category, r)]}" for r in radii)
        print(f"  {category}: {cells}")
    sources = Counter(c.name_source for c in selected)
    print(f"Tên lấy từ brand: {sources['brand']}; không tên, dùng nhãn tạm: {sources['unnamed']}")
    manual_counts = Counter(r["category"] for r in manual_rows)
    print(f"Nguồn thủ công: {dict(manual_counts) or 'không có'}")
    print(f"Đã ghi {DRAFT_PATH.relative_to(ROOT)}: {len(rows)} dòng. Duyệt xong mới chép sang data/pois.csv.")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
