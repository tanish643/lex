import pytest

from lexai.rag.embed import VOYAGE_DIM, embed_texts


@pytest.mark.integration
def test_embed_single_document_returns_expected_dim():
    vectors = embed_texts(["hello world"], input_type="document")
    assert len(vectors) == 1
    assert len(vectors[0]) == VOYAGE_DIM
    assert all(isinstance(v, float) for v in vectors[0])


@pytest.mark.integration
def test_embed_batch_returns_one_vector_per_text():
    texts = ["contract law in India", "Section 302 IPC", "Article 21 right to life"]
    vectors = embed_texts(texts, input_type="document")
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == VOYAGE_DIM


@pytest.mark.integration
def test_embed_query_vs_document_produces_different_vectors():
    # voyage-law-2 is asymmetric — same text with different input_type
    # should yield different vectors.
    [doc_vec] = embed_texts(["bail application"], input_type="document")
    [qry_vec] = embed_texts(["bail application"], input_type="query")
    assert doc_vec != qry_vec


def test_embed_empty_list_returns_empty():
    # no API call needed for empty input
    assert embed_texts([], input_type="document") == []


def test_embed_rejects_invalid_input_type():
    with pytest.raises(ValueError):
        embed_texts(["x"], input_type="bogus")  # type: ignore[arg-type]
