from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Define main database
URL_DATABASE = "sqlite:///./data.db"
MainEngine = create_engine(URL_DATABASE, connect_args={"check_same_thread": False})
MainSessionLocal = sessionmaker(autocommit = False, autoflush = False, bind=MainEngine)
MainBase = declarative_base()

def get_main_db():
    db = MainSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Define temporary database for PDF extraction
URL_DATABASE = "sqlite:///./temp_data.db"
PdfEngine = create_engine(URL_DATABASE, connect_args={"check_same_thread": False})
PdfSessionLocal = sessionmaker(autocommit = False, autoflush = False, bind=PdfEngine)
PdfBase = declarative_base()

def get_pdf_db():
    db = PdfSessionLocal()
    try:
        yield db
    finally:
        db.close()