from pathlib import Path

import pytest

from lexai.ingest.pdf import extract_pdf_text

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "moots" / "sample.pdf"


@pytest.mark.skipif(not FIXTURE.exists(), reason="sample.pdf fixture missing")
def test_extract_pdf_text_returns_substantive_text():
    text = extract_pdf_text(FIXTURE)
    assert len(text) > 500
    assert "\n" in text


@pytest.mark.skipif(not FIXTURE.exists(), reason="sample.pdf fixture missing")
def test_extract_pdf_text_concatenates_pages_with_blank_line():
    text = extract_pdf_text(FIXTURE)
    # multi-page PDFs should be separated by \n\n page breaks
    assert "\n\n" in text


def test_extract_pdf_text_accepts_path_or_str(tmp_path: Path):
    missing = tmp_path / "does-not-exist.pdf"
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(missing)
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(str(missing))
