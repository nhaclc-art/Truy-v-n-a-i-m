import pytest

from src import db
from src.config import load_app_config, load_campus
from src.evaluation import (
    QREL_FIELDS,
    check_qrels,
    evaluate,
    label_rows,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    sign_rows,
    summarize,
)

CFG = load_app_config()
REF = load_campus()["reference_point"]


def query(qid, text, radius, category=None):
    return {"query_id": qid, "query": text, "lat": REF["lat"], "lon": REF["lon"], "radius_m": radius, "category": category}


QUERIES = [
    query("Q1", "van phong pham", 2000, "vpp_photocopy"),
    query("Q2", "khongtontai", 1000),
    query("Q3", "pho", 1000, "an_uong"),
]
LABELS = {
    ("Q1", "fx-vpp-hongha"): 1,
    ("Q1", "fx-photo-ngoclan"): 1,
    ("Q2", "fx-circle-k"): 0,
    ("Q2", "fx-vpp-hongha"): 0,
    ("Q2", "fx-com-tam"): 0,
    ("Q2", "fx-photo-ngoclan"): 0,
    ("Q2", "fx-pho-dakao"): 0,
    ("Q3", "fx-pho-dakao"): 1,
    ("Q3", "fx-com-tam"): 1,  # nhãn giả định cho test: liên quan nhưng không khớp từ "pho"
}


def qrel(qid, pid, relevance, reviewed=True):
    row = dict.fromkeys(QREL_FIELDS, "")
    row.update(query_id=qid, poi_id=pid, relevance=str(relevance))
    if reviewed:
        row.update(reviewed_by="Người duyệt", reviewed_at="2026-09-19")
    return row


QRELS = [qrel(q, p, r) for (q, p), r in LABELS.items()]


@pytest.fixture
def conn(fixture_db):
    c = db.connect(fixture_db)
    yield c
    c.close()


def test_precision_counts_missing_positions_as_not_relevant():
    assert precision_at_k(["a", "b", "c"], {"a", "c"}, 5) == pytest.approx(0.4)


def test_recall_uses_all_relevant_and_is_na_without_answers():
    assert recall_at_k(["a", "b"], {"a", "z", "y"}, 5) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "b"], set(), 5) is None


def test_ndcg_uses_exponential_gain():
    # Ví dụ trong docs/planning/00: nhãn [1, 2] so với ideal [2, 1] cho NDCG@2 ≈ 0.796708 với gain 2^rel − 1.
    assert ndcg_at_k(["x", "y"], {"x": 1, "y": 2}, 2) == pytest.approx(0.796708, abs=1e-6)
    assert ndcg_at_k(["x"], {"x": 0, "y": 0}, 5) is None


def test_label_rows_cover_scope_in_id_order_and_keep_existing_labels(conn):
    existing = [qrel("Q3", "fx-pho-dakao", 1), qrel("Q3", "fx-nha-tro", 1)]
    rows, dropped = label_rows(conn, [QUERIES[2]], existing)

    assert [r["poi_id"] for r in rows] == ["fx-com-tam", "fx-pho-dakao"]
    assert rows[0]["relevance"] == "" and rows[1]["relevance"] == "1"
    assert rows[1]["poi_name"] == "Phở Bò Đa Kao"
    assert [r["poi_id"] for r in dropped] == ["fx-nha-tro"]


def test_check_requires_full_scope_valid_relevance_and_review(conn):
    assert check_qrels(conn, QUERIES, QRELS) == ([], 0)

    missing = [r for r in QRELS if r["poi_id"] != "fx-com-tam" or r["query_id"] != "Q3"]
    errors, _ = check_qrels(conn, QUERIES, missing)
    assert any("Q3: 1 POI trong phạm vi chưa có dòng nhãn" in e for e in errors)

    blank = QRELS[:-1] + [qrel("Q3", "fx-com-tam", "")]
    assert any("relevance phải là 0, 1 hoặc 2" in e for e in check_qrels(conn, QUERIES, blank)[0])

    unreviewed = QRELS[:-1] + [qrel("Q3", "fx-com-tam", 1, reviewed=False)]
    assert check_qrels(conn, QUERIES, unreviewed) == ([], 1)


def test_sign_rows_fills_only_unreviewed_rows_and_refuses_unlabeled():
    rows = [qrel("Q1", "a", 1, reviewed=False), qrel("Q1", "b", 0)]
    signed_rows, signed, errors = sign_rows(rows, "Người mới", "2026-09-20")

    assert (signed, errors) == (1, [])
    assert (signed_rows[0]["reviewed_by"], signed_rows[0]["reviewed_at"]) == ("Người mới", "2026-09-20")
    assert signed_rows[1]["reviewed_by"] == "Người duyệt"

    _, signed, errors = sign_rows([qrel("Q1", "a", "", reviewed=False)], "Người mới", "2026-09-20")
    assert signed == 0 and errors


def test_evaluate_all_modes_on_the_same_candidates(conn):
    results, metrics = evaluate(conn, CFG, REF, QUERIES, QRELS)
    by_key = {(m["query_id"], m["mode"]): m for m in metrics}

    for mode in ("bm25", "distance", "combined"):
        q1 = by_key[("Q1", mode)]
        assert (q1["precision_at_5"], q1["recall_at_5"]) == (pytest.approx(0.4), pytest.approx(1.0))

        q2 = by_key[("Q2", mode)]
        assert (q2["returned_count"], q2["precision_at_5"], q2["recall_at_5"]) == (0, 0.0, None)

        q3 = by_key[("Q3", mode)]
        assert q3["recall_at_5"] == pytest.approx(0.5)
        assert q3["missed_by_retrieval"] == "fx-com-tam"

    assert {r["mode"] for r in results} == {"bm25", "distance", "combined"}

    summary = summarize(metrics)["combined"]
    assert summary["r5_excluded"] == 1
    assert summary["r5"] == pytest.approx(0.75)
    assert summary["p5_all"] == pytest.approx((0.4 + 0.0 + 0.2) / 3)
    assert summary["p5_answered"] == pytest.approx((0.4 + 0.2) / 2)
