"""Dựng truy vấn từ chữ đọc được trên ảnh biển hiệu (OCR chạy trong trình duyệt).

Chữ trên biển hiệu là một "truy vấn dài và nhiễu": tên quán lẫn với số điện thoại, địa chỉ, khẩu hiệu,
và lỗi nhận dạng. Nếu tìm như người gõ (nối AND) thì gần như luôn rỗng. Cách xử lý (query-by-document):
1. Chuẩn hóa như truy vấn thường; sửa nhầm lẫn ký tự hay gặp của OCR trong token lẫn chữ và số
   ("c1rcle" → "circle") khi bản sửa có trong từ vựng.
2. Sửa lỗi gõ như src/spell.py (gộp, tách, sửa chữ).
3. Bỏ token không giúp phân biệt: số (số nhà, điện thoại), token không có trong từ vựng (không thể khớp),
   token có trong hơn max_df_ratio tài liệu (FTS5 cũng kẹp IDF của chúng về gần 0).
4. Giữ tối đa max_query_tokens token hiếm nhất (DF nhỏ ~ IDF lớn), theo thứ tự xuất hiện.
Truy vấn kết quả được tìm với match = "any" (OR): BM25 ưu tiên địa điểm khớp nhiều từ và từ hiếm.
"""
import sqlite3

from src.normalize import analyze
from src.spell import correct_tokens, vocabulary

# Nhầm lẫn ký tự thường gặp của OCR giữa số và chữ.
OCR_CONFUSIONS = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})


def fix_confusions(tokens: list[str], vocab: dict[str, int]) -> tuple[list[str], list[dict]]:
    out, fixes = [], []
    for t in tokens:
        mixed = any(c.isdigit() for c in t) and any(c.isalpha() for c in t)
        if mixed and t not in vocab:
            candidate = t.translate(OCR_CONFUSIONS)
            if candidate in vocab:
                fixes.append({"from": t, "to": candidate, "kind": "ocr"})
                t = candidate
        out.append(t)
    return out, fixes


def build_ocr_query(conn: sqlite3.Connection, text: str, cfg: dict) -> dict:
    ocfg = cfg["ocr"]
    vocab = vocabulary(conn)
    total = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0] or 1
    read = analyze(text)[: ocfg["max_input_tokens"]]
    tokens, fixes = fix_confusions(read, vocab)
    tokens, corrections = correct_tokens(tokens, vocab, cfg)

    candidates, dropped, seen = [], [], set()
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        if t.isdigit():
            dropped.append({"token": t, "reason": "số (số nhà, điện thoại…)"})
        elif t not in vocab:
            dropped.append({"token": t, "reason": "không có trong dữ liệu"})
        elif vocab[t] / total > ocfg["max_df_ratio"]:
            dropped.append({"token": t, "reason": "quá phổ biến"})
        else:
            candidates.append(t)

    rarest = set(sorted(candidates, key=lambda t: (vocab[t], candidates.index(t)))[: ocfg["max_query_tokens"]])
    kept = [t for t in candidates if t in rarest]
    for t in candidates:
        if t not in rarest:
            dropped.append({"token": t, "reason": f"ngoài {ocfg['max_query_tokens']} từ hiếm nhất"})
    return {
        "text": text,
        "tokens_read": read,
        "query": " ".join(kept),
        "kept": [{"token": t, "df": vocab[t]} for t in kept],
        "dropped": dropped,
        "corrections": fixes + corrections,
    }
