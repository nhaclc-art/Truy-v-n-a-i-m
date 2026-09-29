import pytest

from src import db
from src.config import load_app_config, load_campus
from src.search import SearchError, parse_params, search
from src.spell import correct_tokens, is_vietnamese_syllable, nearest_word, osa_distance, split_word, vocabulary

CFG = load_app_config()
REF = load_campus()["reference_point"]


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def run(conn, **args):
    return search(conn, parse_params({k: str(v) for k, v in args.items()}, CFG, REF), CFG)


def ids(result) -> list[str]:
    return [i["id"] for i in result["items"]]


@pytest.mark.parametrize(
    "a, b, limit, expected",
    [("ca", "ac", 1, 1), ("circel", "circle", 2, 1), ("kitten", "sitting", 3, 3), ("abc", "abcdef", 1, 2), ("pizza", "pizza", 2, 0)],
)
def test_osa_distance_counts_transpositions_and_stops_at_limit(a, b, limit, expected):
    assert osa_distance(a, b, limit) == expected


@pytest.mark.parametrize("token", ["sang", "nguyen", "truong", "xoong", "tieu", "tien", "quyen", "gia", "pho"])
def test_valid_vietnamese_syllables_are_recognized(token):
    assert is_vietnamese_syllable(token)


@pytest.mark.parametrize("token", ["troo", "phee", "caay", "photocopy", "buyts", "suwa", "xawng", "comm", "tie"])
def test_typos_and_foreign_words_are_not_syllables(token):
    assert not is_vietnamese_syllable(token)


def test_split_word_prefers_fewest_known_parts():
    vocab = {"van": 1, "phong": 1, "pham": 1, "circle": 1, "k": 1, "com": 1, "m": 1}
    assert split_word("vanphongpham", vocab) == ["van", "phong", "pham"]
    assert split_word("circlek", vocab) == ["circle", "k"]
    # Token ngắn không được tách ra phần 1 ký tự.
    assert split_word("comm", vocab) is None


def test_nearest_word_uses_document_frequency_to_break_ties_and_knows_aliases():
    vocab = {"tro": 2, "trong": 1, "ca": 3, "phe": 3}
    assert nearest_word("trooj", vocab, 2) == ("tro",)
    assert nearest_word("cofee", vocab, 1) == ("ca", "phe")  # viết tắt "coffee"
    assert nearest_word("zzzz", vocab, 1) is None


def test_correct_tokens_merges_splits_edits_and_keeps_valid_words():
    vocab = {"circle": 1, "k": 1, "photocopy": 2, "xe": 3, "buyt": 3, "hang": 5}
    tokens, corrections = correct_tokens(["circ", "le", "photocoppy", "xebuyt", "sang", "abc"], vocab, CFG)

    assert tokens == ["circle", "photocopy", "xe", "buyt", "sang", "abc"]
    assert [c["kind"] for c in corrections] == ["merge", "edit", "split"]
    # "sang" (sáng) là âm tiết hợp lệ nên không bị đổi thành "hang"; "abc" quá ngắn.


def test_spoken_loanword_syllables_are_merged():
    # Bộ nhận giọng nói tiếng Việt hay trả "phô tô cóp pi" cho "photocopy".
    vocab = {"photocopy": 2, "pho": 1, "com": 3}
    assert correct_tokens(["pho", "to", "cop", "pi"], vocab, CFG) == (
        ["photocopy"],
        [{"from": "pho to cop pi", "to": "photocopy", "kind": "merge"}],
    )
    # Hai âm tiết ghép thành viết tắt "photo" → "photocopy".
    assert correct_tokens(["pho", "to"], {"photocopy": 2, "pho": 1}, CFG)[0] == ["photocopy"]
    # Hai âm tiết không khớp đúng từ nào thì không gộp gần đúng.
    assert correct_tokens(["com", "tamm"], {"com": 3, "tam": 2}, CFG)[0] == ["com", "tam"]


def test_word_error_rate():
    from src.evaluation import word_error_rate

    assert word_error_rate(["cay", "xang"], ["cay", "xang"]) == 0
    assert word_error_rate(["cay", "xang"], ["cay", "sang"]) == 0.5
    assert word_error_rate(["photocopy"], ["pho", "to", "cop", "pi"]) == 4.0
    assert word_error_rate([], ["x"]) is None


def test_vocabulary_comes_from_the_index(conn):
    vocab = vocabulary(conn)
    assert vocab["photocopy"] == 2 and vocab["circle"] == 1
    assert "vpp" not in vocab  # viết tắt đã được mở rộng khi lập chỉ mục


def test_typo_query_finds_the_same_places_and_reports_the_correction(conn):
    exact = run(conn, q="photocopy", radius_m=2000)
    typo = run(conn, q="photocoppy", radius_m=2000)

    assert ids(typo) == ids(exact) and ids(typo)
    assert typo["meta"]["corrections"] == [{"from": "photocoppy", "to": "photocopy", "kind": "edit"}]
    assert typo["meta"]["query_normalized"] == "photocopy"
    assert typo["meta"]["query_as_typed"] == "photocoppy"


def test_spell_off_searches_exactly_as_typed(conn):
    result = run(conn, q="photocoppy", radius_m=2000, spell=0)

    assert result["items"] == []
    assert result["meta"]["corrections"] == [] and result["meta"]["spell"] is False


def test_glued_words_are_split(conn):
    assert ids(run(conn, q="circlek", radius_m=2000)) == ["fx-circle-k"]


def test_known_and_valid_words_are_not_touched(conn):
    result = run(conn, q="van phong pham sang", radius_m=2000)

    assert result["meta"]["corrections"] == []
    assert result["items"] == []


def test_invalid_spell_parameter_is_rejected():
    with pytest.raises(SearchError, match="spell"):
        parse_params({"spell": "maybe"}, CFG, REF)
