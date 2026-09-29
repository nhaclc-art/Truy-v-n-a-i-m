"""Chuẩn hóa văn bản tiếng Việt, dùng chung cho chỉ mục và truy vấn.

Tách từ theo khoảng trắng là baseline, chưa phải tách từ tiếng Việt hoàn chỉnh.
"""
import re
import unicodedata
from functools import lru_cache

from src.config import load_aliases

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str | None) -> str:
    """Bỏ dấu, đổi đ→d, chữ thường; mọi ký tự không phải chữ/số thành một khoảng trắng."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.lower().replace("đ", "d")
    return " ".join(_NON_ALNUM.sub(" ", lowered).split())


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, tuple[str, ...]]:
    return {normalize(k): tuple(normalize(v).split()) for k, v in load_aliases().items()}


def analyze(text: str | None) -> list[str]:
    """Chuẩn hóa, tách token rồi mở rộng alias. Đổi config/aliases.json cần khởi động lại app."""
    aliases = _alias_map()
    tokens: list[str] = []
    for token in normalize(text).split():
        tokens.extend(aliases.get(token, (token,)))
    return tokens
