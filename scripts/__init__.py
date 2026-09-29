"""Lệnh CLI của GeoRank; chạy từ thư mục gốc dự án bằng `python -m scripts.<tên>`."""
import sys


def use_utf8_stdio() -> None:
    # Khi stdout bị chuyển hướng trên Windows, Python dùng code page ANSI và lỗi với tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
