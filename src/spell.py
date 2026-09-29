"""Sửa lỗi gõ trong truy vấn (phương án B). Chỉ sửa token không có trong từ vựng của chỉ mục.

Từ vựng lấy thẳng từ chỉ mục FTS5 qua bảng ảo fts5vocab (từ, số tài liệu chứa từ), nên luôn khớp
với dữ liệu đang có. Các bước, theo thứ tự:
1. Gộp hai token liền nhau khi phần ghép là một từ trong từ vựng và ít nhất một token chưa có
   ("may cha" → "maycha", "piz za" → "pizza").
2. Tách token dính thành các từ có sẵn ("vanphongpham" → "van phong pham", "circlek" → "circle k").
3. Còn lạ thì tìm từ gần nhất theo khoảng cách Damerau–Levenshtein (dạng OSA, tính cả hoán vị hai
   ký tự liền nhau) trong từ vựng và danh sách viết tắt: tối đa 1 lỗi với từ 4 ký tự, 2 lỗi từ
   5 ký tự trở lên. Hòa thì chọn từ xuất hiện trong nhiều tài liệu hơn.
Không sửa: token ngắn hơn 4 ký tự, số, và token là một âm tiết tiếng Việt hợp lệ (không dấu). Âm
tiết hợp lệ như "sang" (sáng) chỉ là từ không có trong dữ liệu, không phải lỗi gõ; sửa nó thành
"hang" sẽ đổi nghĩa truy vấn. Lỗi dấu (gõ "trà sũa") đã được bước chuẩn hóa bỏ dấu xử lý từ trước.
"""
import re
import sqlite3

from src import db
from src.normalize import _alias_map

_vocab_cache: dict[str, dict[str, int]] = {}

# Âm tiết tiếng Việt sau khi bỏ dấu: phụ âm đầu? + vần + phụ âm cuối?. Các vần "ie", "ye", "uo", "oo"
# luôn cần phụ âm cuối (tiên, yên, muốn, xoong).
_INITIAL = r"(?:ngh|ch|gh|gi|kh|ng|nh|ph|qu|th|tr|[bcdghklmnprstvx])?"
_OPEN = r"(?:uye|uya|uyu|oai|oay|oeo|uoi|uou|ieu|yeu|uay|uai|oao|ai|ao|au|ay|eo|eu|ia|iu|oa|oe|oi|ua|ue|ui|uu|uy|ya|a|e|i|o|u|y)"
_CLOSED = r"(?:uye|uyu|oai|oay|ie|ye|uo|oo|oa|oe|ua|ue|uy|a|e|i|o|u|y)"
_FINAL = r"(?:ch|ng|nh|c|m|n|p|t)"
_SYLLABLE = re.compile(rf"^{_INITIAL}(?:{_OPEN}{_FINAL}?|{_CLOSED}{_FINAL})$")


def is_vietnamese_syllable(token: str) -> bool:
    return bool(_SYLLABLE.match(token))


def vocabulary(conn: sqlite3.Connection) -> dict[str, int]:
    """{từ: số tài liệu chứa từ}, cache theo dataset_version (đổi dữ liệu thì version đổi)."""
    version = db.get_meta(conn, "dataset_version")
    if version and version in _vocab_cache:
        return _vocab_cache[version]
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.poi_vocab USING fts5vocab(main, poi_fts, row)")
    vocab = {term: doc for term, doc in conn.execute("SELECT term, doc FROM temp.poi_vocab")}
    if version:
        _vocab_cache[version] = vocab
    return vocab


def osa_distance(a: str, b: str, limit: int) -> int:
    """Khoảng cách Damerau–Levenshtein (optimal string alignment); trả limit + 1 khi vượt limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], before[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        before, prev = prev, cur
    return prev[-1]


def split_word(token: str, vocab: dict[str, int]) -> list[str] | None:
    """Tách token thành ít phần nhất, mỗi phần là từ trong từ vựng, dài ≥ 2 ký tự.

    Riêng phần cuối được dài 1 ký tự khi token từ 6 ký tự trở lên ("circlek" → "circle k"), để từ
    ngắn như "comm" không bị tách thành "com m".
    """
    n = len(token)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    for end in range(1, n + 1):
        for start in range(end):
            part = token[start:end]
            if best[start] is None or part not in vocab:
                continue
            if len(part) < 2 and not (end == n and n >= 6):
                continue
            candidate = best[start] + [part]
            if best[end] is None or len(candidate) < len(best[end]):
                best[end] = candidate
    parts = best[n]
    return parts if parts and len(parts) >= 2 else None


def nearest_word(token: str, vocab: dict[str, int], limit: int) -> tuple[str, ...] | None:
    """Từ gần nhất (đã mở rộng viết tắt) trong khoảng limit lỗi, hoặc None."""
    aliases = _alias_map()
    best_key, best = None, None
    candidates = [(w, (w,), df) for w, df in vocab.items()]
    candidates += [(key, expansion, min(vocab.get(t, 0) for t in expansion)) for key, expansion in aliases.items()]
    for word, expansion, df in candidates:
        dist = osa_distance(token, word, limit)
        if dist > limit:
            continue
        key = (dist, -df, word)
        if best_key is None or key < best_key:
            best_key, best = key, expansion
    return best


def edit_limit(token: str, scfg: dict) -> int:
    return scfg["max_edits_long"] if len(token) >= scfg["long_len"] else scfg["max_edits_short"]


def merge_runs(tokens: list[str], vocab: dict[str, int], scfg: dict) -> tuple[list[str], list[dict]]:
    """Gộp 2–max_merge token liền nhau có ít nhất một token lạ.

    - Phần ghép trùng đúng một từ trong từ vựng hoặc một viết tắt: gộp ("piz za" → "pizza",
      "pho to" → "photo" → "photocopy").
    - Từ 3 token trở lên và phần ghép dài ≥ 6 ký tự: cho phép gần đúng như bước sửa chữ. Bộ nhận
      giọng nói hay tách từ mượn thành âm tiết ("phô tô cóp pi" → "photocoppi" → "photocopy").
    Ưu tiên cửa sổ dài nhất tại mỗi vị trí.
    """
    aliases = _alias_map()
    out: list[str] = []
    corrections: list[dict] = []
    i = 0
    while i < len(tokens):
        for width in range(min(scfg["max_merge"], len(tokens) - i), 1, -1):
            window = tokens[i : i + width]
            if all(t in vocab for t in window):
                continue
            joined = "".join(window)
            if joined in vocab:
                target = (joined,)
            elif joined in aliases:
                target = aliases[joined]
            elif width >= 3 and len(joined) >= 6:
                target = nearest_word(joined, vocab, edit_limit(joined, scfg))
            else:
                target = None
            if target:
                out.extend(target)
                corrections.append({"from": " ".join(window), "to": " ".join(target), "kind": "merge"})
                i += width
                break
        else:
            out.append(tokens[i])
            i += 1
    return out, corrections


def correct_tokens(tokens: list[str], vocab: dict[str, int], cfg: dict) -> tuple[list[str], list[dict]]:
    """Trả về (token sau khi sửa, danh sách {from, to, kind}). Token đã có trong từ vựng giữ nguyên."""
    scfg = cfg["spell"]
    merged, corrections = merge_runs(tokens, vocab, scfg)

    out: list[str] = []
    for t in merged:
        if t in vocab or t.isdigit() or len(t) < scfg["min_len"] or is_vietnamese_syllable(t):
            out.append(t)
            continue
        parts = split_word(t, vocab)
        if parts:
            out.extend(parts)
            corrections.append({"from": t, "to": " ".join(parts), "kind": "split"})
            continue
        replacement = nearest_word(t, vocab, edit_limit(t, scfg))
        if replacement:
            out.extend(replacement)
            corrections.append({"from": t, "to": " ".join(replacement), "kind": "edit"})
        else:
            out.append(t)
    return out, corrections
