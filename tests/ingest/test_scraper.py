from lexai.ingest.scraper import extract_case_text


def test_extract_case_text_from_html():
    html = """
    <html><body>
      <div class="navigation">Home | Search</div>
      <div class="judgments">
        <p>The appeal is dismissed.</p>
        <p>Costs of Rs 10,000.</p>
      </div>
    </body></html>
    """
    result = extract_case_text(html)
    assert "appeal is dismissed" in result
    assert "10,000" in result
    assert "<p>" not in result
    assert "Home | Search" not in result


def test_extract_case_text_falls_back_when_no_judgments_div():
    html = "<html><body><p>Plain judgment text.</p></body></html>"
    result = extract_case_text(html)
    assert "Plain judgment text." in result


def test_extract_case_text_joins_paragraphs_with_blank_line():
    html = '<div class="judgments"><p>First.</p><p>Second.</p></div>'
    result = extract_case_text(html)
    assert result == "First.\n\nSecond."


def test_extract_case_text_strips_empty_paragraphs():
    html = '<div class="judgments"><p>Real.</p><p>   </p><p>Also real.</p></div>'
    result = extract_case_text(html)
    assert result == "Real.\n\nAlso real."
