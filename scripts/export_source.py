"""Xuất source sạch exports/georank-hcmue-source.zip theo danh sách cho phép (docs/planning/04 §9).

Chỉ lấy file cần để cài, import, chạy, test và tái lập đánh giá. Không lấy DB sinh lại được, venv,
cache, snapshot thô, bản nháp, file nội bộ (STATUS, DECISIONS) hay bản ZIP khác. Sau khi ghi, script
mở lại ZIP để kiểm tra không lọt file cấm và cảnh báo nếu có đường dẫn tuyệt đối trong file văn bản.
"""
import argparse
import hashlib
import re
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import use_utf8_stdio
from src.config import ROOT

ARCHIVE_ROOT = "georank-hcmue"
INCLUDE = (
    ".gitignore",
    "app.py",
    "requirements.txt",
    "pytest.ini",
    "README.md",
    "HUONG_DAN.md",
    "SO_LIEU_BAO_CAO.md",
    "DATA_SOURCES.md",
    "KNOWN_LIMITATIONS.md",
    "THIRD_PARTY_NOTICES.md",
    "MANUAL_CHECKS.md",
    "config",
    "src",
    "scripts",
    "static",
    "tests",
    "data/pois.csv",
    "data/README.md",
    "data/manual",
    "data/updates",
    "data/review_sheet.csv",
    "eval",
)
REQUIRED = ("app.py", "requirements.txt", "README.md", "config/app.json", "data/pois.csv", "static/index.html")
# "tesseract": bộ đọc chữ ~12 MB, người nhận tải lại bằng scripts.vendor_tesseract (README).
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "raw", "exports", "tesseract"}
EXCLUDED_NAMES = {"STATUS.md", "DECISIONS.md", "pois_draft.csv", "Thumbs.db", ".DS_Store"}
FORBIDDEN_NAME = re.compile(r"(\.(db|sqlite3?)(-\w+)?|\.py[cod]|\.zip|\.log)$|^\.env(?!\.example$)", re.IGNORECASE)
ABSOLUTE_PATH = re.compile(r"[A-Za-z]:\\Users\\|/home/[a-z]|/Users/[A-Za-z]")
TEXT_SUFFIXES = {".py", ".md", ".csv", ".json", ".js", ".css", ".html", ".ini", ".txt", ".mjs"}


def is_excluded(rel: Path) -> bool:
    return bool(set(rel.parts) & EXCLUDED_DIRS) or rel.name in EXCLUDED_NAMES or bool(FORBIDDEN_NAME.search(rel.name))


def collect_files(root: Path) -> tuple[list[Path], list[str]]:
    """Trả về (file tương đối sẽ đóng gói, các mục bắt buộc còn thiếu)."""
    files: set[Path] = set()
    for entry in INCLUDE:
        path = root / entry
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [p for p in path.rglob("*") if p.is_file()]
        else:
            continue
        for p in candidates:
            rel = p.relative_to(root)
            if not is_excluded(rel):
                files.add(rel)
    missing = [r for r in REQUIRED if not (root / r).is_file()]
    return sorted(files), missing


def dataset_version(root: Path) -> str:
    db_path = root / "data" / "georank.db"
    if not db_path.exists():
        return "chưa import"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'dataset_version'").fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        conn.close()
    return row[0] if row else "chưa import"


def main() -> int:
    parser = argparse.ArgumentParser(description="Xuất source sạch thành file ZIP.")
    parser.add_argument("--out", type=Path, default=ROOT / "exports" / "georank-hcmue-source.zip")
    parser.add_argument("--release", default="", help="nhãn phiên bản ghi vào MANIFEST.txt, ví dụ v1.0-giuaky")
    args = parser.parse_args()

    files, missing = collect_files(ROOT)
    if missing:
        print(f"Thiếu file bắt buộc: {', '.join(missing)}", file=sys.stderr)
        return 1

    manifest = [
        f"GeoRank HCMUE source package {args.release}".rstrip(),
        f"Tạo lúc (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"dataset_version lúc xuất: {dataset_version(ROOT)}",
        f"Số file: {len(files)}",
        "",
    ]
    warnings = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in files:
            content = (ROOT / rel).read_bytes()
            archive.writestr(f"{ARCHIVE_ROOT}/{rel.as_posix()}", content)
            manifest.append(f"{hashlib.sha256(content).hexdigest()}  {rel.as_posix()}")
            if rel.suffix in TEXT_SUFFIXES and ABSOLUTE_PATH.search(content.decode("utf-8", errors="ignore")):
                warnings.append(rel.as_posix())
        archive.writestr(f"{ARCHIVE_ROOT}/MANIFEST.txt", "\n".join(manifest) + "\n")

    with zipfile.ZipFile(args.out) as archive:
        leaked = [n for n in archive.namelist() if is_excluded(Path(n.split("/", 1)[1]))]
    if leaked:
        args.out.unlink()
        print(f"LỖI: file cấm lọt vào ZIP, đã xóa ZIP: {', '.join(leaked)}", file=sys.stderr)
        return 1

    size_kb = args.out.stat().st_size / 1024
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"Đã ghi {args.out.name}: {len(files)} file, {size_kb:.0f} KB, sha256 {digest}")
    for name in warnings:
        print(f"Cảnh báo: {name} có vẻ chứa đường dẫn tuyệt đối trên máy cá nhân")
    return 0


if __name__ == "__main__":
    use_utf8_stdio()
    sys.exit(main())
