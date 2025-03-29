import pdfplumber
from io import BytesIO
from sqlalchemy.orm import Session
from backend.models import ExtractedWord

def extract_pdf_to_db(pdf_stream: BytesIO, source_label: str, db_session: Session):
    with pdfplumber.open(pdf_stream) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["upright"])

            for word_info in words:
                word = word_info.get("text", "")

                db_word = ExtractedWord(
                    word=word,
                    page_no=page_number,
                    word_tag="",
                    item_no=None,
                    source_table=source_label
                )
                db_session.add(db_word)
    db_session.commit()