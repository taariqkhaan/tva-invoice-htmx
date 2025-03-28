from main_database import MainBase
from pdf_database import PdfBase
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship


class Project(MainBase):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    wo_date = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    wo_number = Column(String, nullable=False)
    bmcd_number = Column(String, nullable=False)
    po_number = Column(String, nullable=True)
    tao_number = Column(String, nullable=True)
    contract_number = Column(String, nullable=True)
    total_labor_amount = Column(Float, default=0.0)
    total_expenses_amount = Column(Float, default=0.0)
    total_travel_amount = Column(Float, default=0.0)
    total_tier_fee = Column(Float, default=0.0)
    total_budget_amount = Column(Float, default=0.0)

    # Relationship with Subtask
    subtasks = relationship("Subtask", back_populates="project", cascade="all, delete-orphan")


class Subtask(MainBase):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    subtask_name = Column(String, nullable=False)  # Required: Physical, P&C, Telecom, etc.
    alias = Column(String, nullable=False) # B9, M2, N1 etc.
    short_code = Column(String, nullable=False)
    line_item = Column(Integer, default=0)
    budget_category = Column(String, nullable=False) # labor, expense etc.
    category_amount = Column(Float, default=0.0)

    project = relationship("Project", back_populates="subtasks")
    invoices = relationship("Invoice", back_populates="subtask", cascade="all, delete-orphan")


class Invoice(MainBase):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    subtask_id = Column(Integer, ForeignKey("subtasks.id", ondelete="CASCADE"), nullable=False)
    tier_fee_percentage = Column(Float, default=0.0)
    invoice_percentage = Column(Float, default=0.0)
    invoice_amount = Column(Float, default=0.0)
    invoice_number = Column(String, nullable=False)
    invoice_through_date = Column(String, nullable=False)
    invoice_creation_date = Column(String, nullable=False)

    subtask = relationship("Subtask", back_populates="invoices")


class ExtractedWord(PdfBase):
    __tablename__ = "extracted_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String)
    x1 = Column(Float)
    y1 = Column(Float)
    x2 = Column(Float)
    y2 = Column(Float)
    page_no = Column(Integer)
    page_rot = Column(Integer)
    word_rot = Column(Integer)
    word_tag = Column(String, nullable=True)
    item_no = Column(Integer, nullable=True)
    color_flag = Column(Integer, nullable=True)
    source_table = Column(String)