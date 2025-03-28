from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager

# Define database location URL
URL_DATABASE = "sqlite:///./temp_data.db"

# Create Engine
PdfEngine = create_engine(URL_DATABASE, connect_args={"check_same_thread": False})

# Create a SessionLocal class
PdfSessionLocal = sessionmaker(autocommit = False, autoflush = False, bind=PdfEngine)

# Create a Base class for models
PdfBase = declarative_base()


def get_pdf_db():
    db = PdfSessionLocal()
    try:
        yield db
    finally:
        db.close()