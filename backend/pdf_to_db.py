import pdfplumber
from io import BytesIO
from sqlalchemy.orm import Session
from models import ExtractedWord

def extract_pdf_to_db(pdf_stream: BytesIO, source_label: str, db_session: Session):
    with pdfplumber.open(pdf_stream) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            rotation = page.rotation or 0
            words = page.extract_words(extra_attrs=["upright"])

            for word_info in words:
                word = word_info.get("text", "")
                x0 = word_info.get("x0", 0.0)
                top = word_info.get("top", 0.0)
                x1 = word_info.get("x1", 0.0)
                bottom = word_info.get("bottom", 0.0)
                upright = word_info.get("upright", True)

                word_rotation = 0 if upright else 90
                y1 = page.height - top
                y2 = page.height - bottom

                db_word = ExtractedWord(
                    word=word,
                    x1=x0,
                    y1=y2,
                    x2=x1,
                    y2=y1,
                    page_no=page_number,
                    page_rot=rotation,
                    word_rot=word_rotation,
                    word_tag="",
                    item_no=None,
                    color_flag=None,
                    source_table=source_label
                )

                db_session.add(db_word)

    db_session.commit()