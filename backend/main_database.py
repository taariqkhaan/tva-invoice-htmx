from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Define database location URL
URL_DATABASE = "sqlite:///./data.db"

# Create Engine
MainEngine = create_engine(URL_DATABASE, connect_args={"check_same_thread": False})

# Create a SessionLocal class
MainSessionLocal = sessionmaker(autocommit = False, autoflush = False, bind=MainEngine)

# Create a Base class for models
MainBase = declarative_base()


def get_main_db():
    db = MainSessionLocal()
    try:
        yield db
    finally:
        db.close()