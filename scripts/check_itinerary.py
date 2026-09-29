"""Kiểm tra nhanh (thăm dò) lập lộ trình nhiều chặng trên dữ liệu thật.

Không phải đánh giá IR: lộ trình là bài toán chọn địa điểm theo chuỗi, không có khái niệm "địa điểm
liên quan" như R5 (P@5/Recall@5/nDCG@5 không áp dụng ở đây). Script này chỉ in ra kích thước ứng viên
mỗi chặng, số tổ hợp đã xét, số lộ trình lọt ngân sách và lộ trình tốt nhất, để người dùng tự soát
bằng mắt trước khi kiểm trên giao diện (xem HUONG_DAN.md mục 10F). Ghi kèm eval/itinerary_examples.md.
"""
import sys

from scripts import use_utf8_stdio
from src import db
from src.config import ROOT, load_app_config, load_campus
from src.itinerary import ItineraryParams, plan

EXAMPLES = [
    # "Ba chặng mặc định" khớp đúng giá trị gợi ý sẵn trên giao diện; chặng "phim" luôn RỖNG vì
    # corpus không có danh mục rạp phim (đã ghi trong KNOWN_LIMITATIONS.md) — đây là kết quả đúng,
    # không phải lỗi. "Ba chặng có thật trong dữ liệu" đổi chặng cuối để cho thấy đường đi đủ 3 chặng.
    ("Ba chặng mặc định (giống giao diện)", ("cà phê", "cơm", "phim"), 3000),
    ("Ba chặng có thật trong dữ liệu", ("cà phê", "cơm", "xe buýt"), 3000),
    ("Ngân sách hẹp", ("cà phê", "cơm", "phim"), 1500),
    ("Hai chặng", ("photocopy", "cây xăng"), 2000),
    ("Bốn chặng", ("cà phê", "photocopy", "cây xăng", "xe buýt"), 5000),
]


def fmt_m(m: float) -> str:
    return f"{m:.0f} m" if m < 1000 else f"{m / 1000:.2f} km"


def main() -> int:
    cfg = load_app_config()
    ref = load_campus()["reference_point"]
    icfg = cfg["itinerary"]

    conn = db.connect()
    lines = ["# Ví dụ lập lộ trình nhiều chặng (thăm dò, không phải đánh giá IR)", "", f"Dataset: `{db.get_meta(conn, 'dataset_version')}`.", ""]
    try:
        for title, legs, max_distance_m in EXAMPLES:
            params = ItineraryParams(
                legs=legs,
                lat=ref["lat"],
                lon=ref["lon"],
                origin_mode="reference",
                max_distance_m=max_distance_m,
                dwell_min=tuple(icfg["default_dwell_min"] for _ in legs),
                limit=icfg["max_results"],
            )
            result = plan(conn, cfg, params)
            print(f"\n== {title}: {' → '.join(legs)} (ngân sách {fmt_m(max_distance_m)}) ==")
            for leg in result["legs"]:
                print(f"  chặng '{leg['query']}': {leg['candidates_considered']} ứng viên xét" + (" (RỖNG)" if leg["empty"] else ""))
            print(f"  tổ hợp đã xét: {result['combos_considered']}; trong ngân sách: {result['combos_within_distance']}")
            lines.append(f"## {title}: {' → '.join(legs)} (ngân sách {fmt_m(max_distance_m)})")
            lines.append("")
            lines.append(f"- Tổ hợp đã xét: {result['combos_considered']}; trong ngân sách: {result['combos_within_distance']}.")
            if result["routes"]:
                best = result["routes"][0]
                stops = " → ".join(s["name"] for s in best["stops"])
                print(f"  lộ trình tốt nhất: {stops} — tổng {fmt_m(best['total_distance_m'])}, ~{round(best['total_time_min'])} phút")
                lines.append(f"- Lộ trình tốt nhất: {stops} — tổng {fmt_m(best['total_distance_m'])}, ~{round(best['total_time_min'])} phút.")
                lines.append(f"- Số lộ trình trả về: {len(result['routes'])}.")
            else:
                reason = "một chặng rỗng hoặc trùng địa điểm" if result["min_total_distance_m"] is None else f"ngắn nhất tìm được {fmt_m(result['min_total_distance_m'])}"
                print(f"  không có lộ trình nào lọt ngân sách ({reason})")
                lines.append(f"- Không có lộ trình nào lọt ngân sách ({reason}).")
            lines.append("")
    finally:
        conn.close()

    (ROOT / "eval" / "itinerary_examples.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nĐã ghi eval/itinerary_examples.md")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
