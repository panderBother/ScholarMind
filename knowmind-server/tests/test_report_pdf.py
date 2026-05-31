from app.services.report_pdf_service import markdown_to_pdf_bytes


def test_markdown_to_pdf_bytes() -> None:
    data = markdown_to_pdf_bytes(
        title="测试报告",
        markdown="## 摘要\n\n这是一段正文。",
    )
    assert isinstance(data, bytes)
    assert len(data) > 100
    assert data[:4] == b"%PDF"
