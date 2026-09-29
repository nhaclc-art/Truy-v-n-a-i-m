from pathlib import Path

from scripts.export_source import collect_files, is_excluded

KEEP = [
    "app.py",
    "requirements.txt",
    "README.md",
    ".gitignore",
    "config/app.json",
    "src/search.py",
    "static/index.html",
    "static/vendor/leaflet/leaflet.js",
    "tests/fixtures/pois_fixture.csv",
    "data/pois.csv",
    "data/manual/nha_tro.csv",
    "eval/qrels.csv",
]
DROP = [
    "data/georank.db",
    "data/georank.db-wal",
    "data/pois_draft.csv",
    "data/raw/osm_20260918.json",
    "src/__pycache__/search.cpython-313.pyc",
    ".venv/Scripts/python.exe",
    ".env",
    "STATUS.md",
    "DECISIONS.md",
    "exports/georank-hcmue-source.zip",
    "docs/secret.md",
]


def make_tree(root: Path, paths: list[str]) -> None:
    for rel in paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")


def test_collect_files_keeps_allowlist_and_drops_generated_or_private(tmp_path):
    make_tree(tmp_path, KEEP + DROP)
    files, missing = collect_files(tmp_path)
    names = {p.as_posix() for p in files}

    assert set(KEEP) <= names
    assert names.isdisjoint(DROP)
    assert missing == []


def test_missing_required_files_are_reported(tmp_path):
    make_tree(tmp_path, ["app.py"])
    _, missing = collect_files(tmp_path)
    assert "data/pois.csv" in missing and "README.md" in missing


def test_env_example_is_allowed_but_env_is_not():
    assert is_excluded(Path(".env"))
    assert is_excluded(Path(".env.local"))
    assert not is_excluded(Path(".env.example"))
