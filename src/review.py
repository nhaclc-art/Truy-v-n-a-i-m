"""Áp kết quả duyệt dữ liệu (data/review_sheet.csv) lên bản nháp corpus để tạo data/pois.csv.

Bản nháp sinh từ nguồn không bị sửa tay; mọi chỉnh sửa và bằng chứng kiểm chứng đi qua bảng duyệt,
nên chạy lại fetch → build_draft → apply_review cho cùng kết quả.
"""
import re
from collections import Counter

from src.geo import valid_lat_lon

# ket_qua → verification_status; None nghĩa là giữ trạng thái cũ, chỉ ghi thêm ghi chú.
REVIEW_RESULTS = {
    "dung": "cross_checked",
    "dung_tai_cho": "field_checked",
    "sai": "cross_checked",
    "dong_cua": "uncertain",
    "khong_ro": None,
}
CORRECTABLE = (("name", "ten_dung"), ("address", "dia_chi_dung"), ("category", "danh_muc_dung"))


def _get(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def parse_coords(text: str) -> tuple[float, float]:
    parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
    if len(parts) != 2:
        raise ValueError(f"toa_do_dung phải dạng 'lat, lon' (đang là '{text}')")
    lat, lon = float(parts[0]), float(parts[1])
    if not valid_lat_lon(lat, lon):
        raise ValueError(f"toa_do_dung ngoài miền hợp lệ ('{text}')")
    return lat, lon


def apply_review(pois: list[dict], reviews: list[dict]) -> tuple[list[dict], list[str], Counter, list[str]]:
    """Trả về (rows, lỗi, số dòng theo kết quả duyệt, id trong bảng duyệt không còn trong bản nháp)."""
    reviewed = {r["id"]: r for r in reviews if _get(r, "ket_qua")}
    errors: list[str] = []
    counts: Counter = Counter()
    rows = []
    for poi in pois:
        row = dict(poi)
        review = reviewed.get(poi["id"])
        if review:
            result = _get(review, "ket_qua")
            who, date = _get(review, "nguoi_kiem_tra"), _get(review, "ngay_kiem_tra")
            if result not in REVIEW_RESULTS:
                errors.append(f"{poi['id']}: ket_qua '{result}' không hợp lệ ({', '.join(REVIEW_RESULTS)})")
            elif not (who and date):
                errors.append(f"{poi['id']}: cần nguoi_kiem_tra và ngay_kiem_tra")
            else:
                if result in ("dung", "dung_tai_cho", "sai"):
                    for field, column in CORRECTABLE:
                        if _get(review, column):
                            row[field] = _get(review, column)
                    if _get(review, "toa_do_dung"):
                        try:
                            lat, lon = parse_coords(_get(review, "toa_do_dung"))
                        except ValueError as exc:
                            errors.append(f"{poi['id']}: {exc}")
                        else:
                            row["lat"], row["lon"] = f"{lat:.7f}", f"{lon:.7f}"
                status = REVIEW_RESULTS[result]
                if status:
                    row["verification_status"] = status
                    row["verified_at"] = date
                note = f"Duyệt {date} ({who}, kết quả: {result}): {_get(review, 'ghi_chu')}".rstrip(": ")
                row["verification_note"] = " ".join(p for p in (_get(poi, "verification_note"), note) if p)
                counts[result] += 1
        rows.append(row)
    stale = sorted(set(reviewed) - {p["id"] for p in pois})
    return rows, errors, counts, stale
