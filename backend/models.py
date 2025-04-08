from backend.database import MainBase, PdfBase
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship


#-----------MAIN DATABASE MODEL-----------

class Project(MainBase):
    __tablename__ = "projects_table"

    id = Column(Integer, primary_key=True, index=True)
    wo_date = Column(String)
    project_name = Column(String)
    wo_number = Column(String)
    bmcd_number = Column(String)
    po_number = Column(String)
    tao_number = Column(String)
    contract_number = Column(String)
    total_labor_amount = Column(Numeric(12, 2), default=0.00)
    total_expenses_amount = Column(Numeric(12, 2), default=0.00)
    total_travel_amount = Column(Numeric(12, 2), default=0.00)
    total_tier_fee = Column(Numeric(12, 2), default=0.00)
    total_budget_amount = Column(Numeric(12, 2), default=0.00)

    subtasks = relationship("Subtask", back_populates="project", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="project", cascade="all, delete-orphan")


class Subtask(MainBase):
    __tablename__ = "subtasks_table"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects_table.id", ondelete="CASCADE"), nullable=False)
    subtask_name = Column(String)
    alias = Column(String)
    short_code = Column(String)
    line_item = Column(Integer, default=0)
    budget_category = Column(String)
    category_amount = Column(Numeric(12, 2), default=0.00)

    project = relationship("Project", back_populates="subtasks")
    invoice_items = relationship("InvoiceAmount", back_populates="subtask", cascade="all, delete-orphan")


class Invoice(MainBase):
    __tablename__ = "invoices_table"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects_table.id", ondelete="CASCADE"), nullable=False)
    tier_fee_percentage = Column(Numeric(12, 2), default=0.00)
    invoice_percentage = Column(Numeric(12, 2), default=0.00)
    invoice_number = Column(String)
    invoice_through_date = Column(String)
    invoice_creation_date = Column(String)

    project = relationship("Project", back_populates="invoices")
    invoice_items = relationship("InvoiceAmount", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceAmount(MainBase):
    __tablename__ = "invoice_amount_table"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices_table.id", ondelete="CASCADE"), nullable=False)
    subtask_id = Column(Integer, ForeignKey("subtasks_table.id", ondelete="CASCADE"), nullable=False)
    invoice_amount = Column(Numeric(12, 2), default=0.00)

    invoice = relationship("Invoice", back_populates="invoice_items")
    subtask = relationship("Subtask", back_populates="invoice_items")




#-----------DATABASE MODEL FOR TEMPORARY TEXT EXTRACTION FROM PDF-----------

class ExtractedWord(PdfBase):
    __tablename__ = "extracted_words_table"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String)
    page_no = Column(Integer)
    word_tag = Column(String)
    item_no = Column(Integer)
    source_table = Column(String)