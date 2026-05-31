from app.utils.http_headers import attachment_content_disposition


def test_attachment_disposition_md_default() -> None:
    cd = attachment_content_disposition("报告")
    assert "filename=\"____.md\"" in cd or ".md" in cd
    assert "UTF-8''" in cd


def test_attachment_disposition_pdf() -> None:
    cd = attachment_content_disposition("研究报告.pdf")
    assert ".pdf" in cd
    assert "attachment;" in cd
