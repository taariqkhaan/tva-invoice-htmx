from pydantic import BaseModel, Field
from typing import List, Optional


class SubtaskResponse(BaseModel):
    id: int
    project_id: int
    subtask_name: str
    alias: str
    short_code: str
    line_item: int
    budget_category: str
    category_amount: float

    class Config:
        from_attributes = True

class ProjectResponse(BaseModel):
    id: int
    wo_date: str
    project_name: str
    wo_number: str
    bmcd_number: str
    total_labor_amount: float = 0.0
    total_expenses_amount: float = 0.0
    total_travel_amount: float = 0.0
    total_tier_fee: float = 0.0
    total_budget_amount: float = 0.0
    subtasks: List[SubtaskResponse] = []

    class Config:
        from_attributes = True


# *************************** Request Models ***************************

class SubtaskCreate(BaseModel):
    subtask_name: str
    alias: str
    short_code: str
    line_item: int = 0
    budget_category: str
    category_amount: float = 0.0

    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    wo_date: str
    project_name: str
    wo_number: str
    bmcd_number: str
    total_labor_amount: float = 0.0
    total_expenses_amount: float = 0.0
    total_travel_amount: float = 0.0
    total_tier_fee: float = 0.0
    total_budget_amount: float = 0.0
    subtasks: Optional[List[SubtaskCreate]] = []

    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    invoice_percentage: float
    tier_fee_percentage: float
    invoice_through_date: str

    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    subtask_id: int
    tier_fee_percentage: float
    invoice_percentage: float
    invoice_amount: float
    invoice_number: str
    invoice_through_date: str
    invoice_creation_date: str

    class Config:
        from_attributes = True

class ProjectInvoiceResponse(BaseModel):
    subtask_name: str
    alias: str
    short_code: str
    line_item: int
    budget_category: str
    invoice_amount: float
    invoice_number: str
    invoice_percentage: float
    tier_fee_percentage: float
    invoice_through_date: str
    invoice_creation_date: str

    class Config:
        from_attributes = True