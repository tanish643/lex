from lexai.ingest.chunk import CaseMetadata, Chunk, chunk_case


def _meta() -> CaseMetadata:
    return CaseMetadata(
        case_slug="test-case-1",
        case_title="Test v Tester",
        citation="AIR 2026 SC 1",
        court="Supreme Court of India",
        year=2026,
        area_of_law="constitutional",
    )


def test_short_text_returns_one_chunk():
    text = "This is a short case text with fewer than five hundred tokens."
    chunks = chunk_case(text, _meta())
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_index == 0
    assert c.case_slug == "test-case-1"
    assert c.case_title == "Test v Tester"
    assert c.text == text


def test_empty_text_returns_no_chunks():
    chunks = chunk_case("", _meta())
    assert chunks == []


def test_long_text_produces_multiple_chunks_with_overlap():
    # 1200 words -> with chunk_size=500, overlap=50, stride=450:
    # chunks start at 0, 450, 900 -> 3 chunks
    words = [f"w{i}" for i in range(1200)]
    text = " ".join(words)
    chunks = chunk_case(text, _meta())
    assert len(chunks) == 3
    assert [c.chunk_index for c in chunks] == [0, 1, 2]

    # chunk 0 holds words 0..499
    assert chunks[0].text.split()[0] == "w0"
    assert chunks[0].text.split()[-1] == "w499"

    # chunk 1 starts 50 words before chunk 0's end (overlap)
    assert chunks[1].text.split()[0] == "w450"
    assert chunks[1].text.split()[-1] == "w949"

    # chunk 2 holds remainder starting at the overlap
    assert chunks[2].text.split()[0] == "w900"
    assert chunks[2].text.split()[-1] == "w1199"


def test_chunk_carries_metadata():
    words = [f"w{i}" for i in range(600)]
    text = " ".join(words)
    chunks = chunk_case(text, _meta())
    assert len(chunks) >= 2
    for c in chunks:
        assert c.case_slug == "test-case-1"
        assert c.citation == "AIR 2026 SC 1"
        assert c.court == "Supreme Court of India"
        assert c.year == 2026
        assert c.area_of_law == "constitutional"
        assert c.chunk_id == f"test-case-1::{c.chunk_index}"


def test_chunk_id_is_unique_per_chunk():
    words = [f"w{i}" for i in range(1500)]
    text = " ".join(words)
    chunks = chunk_case(text, _meta())
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids)


def test_chunk_types():
    chunks = chunk_case("hello world", _meta())
    assert isinstance(chunks[0], Chunk)
