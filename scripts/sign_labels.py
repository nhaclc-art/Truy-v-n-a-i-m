"""Người duyệt ký xác nhận đã xem toàn bộ nhãn trong eval/qrels.csv (R5).

Chỉ chạy SAU KHI đã đọc từng truy vấn và sửa nhãn nếu không đồng ý. Lệnh ghi reviewed_by và
reviewed_at cho mọi dòng chưa có người duyệt; dòng đã có người duyệt giữ nguyên.

Ví dụ: python -m scripts.sign_labels --reviewer "Nguyễn Văn A" --confirm-reviewed
"""
import argparse
import sys
from datetime import date
from pathlib import Path

from scripts import use_utf8_stdio
from src.config import ROOT
from src.evaluation import QREL_FIELDS, read_csv, sign_rows, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Ký xác nhận đã duyệt nhãn trong eval/qrels.csv.")
    parser.add_argument("--reviewer", required=True, help="họ tên người duyệt thật")
    parser.add_argument("--date", default=date.today().isoformat(), help="ngày duyệt, mặc định hôm nay")
    parser.add_argument(
        "--confirm-reviewed",
        action="store_true",
        help="xác nhận đã xem toàn bộ nhãn; thiếu cờ này thì không ghi",
    )
    parser.add_argument("--qrels", type=Path, default=ROOT / "eval" / "qrels.csv")
    args = parser.parse_args()

    reviewer = args.reviewer.strip()
    if not reviewer:
        print("Cần họ tên người duyệt.", file=sys.stderr)
        return 1
    if not args.confirm_reviewed:
        print("Thêm --confirm-reviewed để xác nhận đã xem toàn bộ nhãn trước khi ký.", file=sys.stderr)
        return 1

    rows, signed, errors = sign_rows(read_csv(args.qrels), reviewer, args.date)
    if errors:
        print(f"Không ký. {len(errors)} dòng chưa có nhãn hợp lệ:", file=sys.stderr)
        for message in errors[:20]:
            print(f"  - {message}", file=sys.stderr)
        return 1
    write_csv(args.qrels, rows, QREL_FIELDS)
    print(f"Đã ký {signed} dòng cho người duyệt '{reviewer}' ngày {args.date}; {len(rows) - signed} dòng đã có người duyệt từ trước.")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
