from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

#-----------------------------------------------------------------------------------------------------------------------
class SubtaskCreate(BaseModel):
    subtask_name: str
    alias: str
    short_code: str
    line_item: int = 0
    budget_category: str
    category_amount: Decimal = Decimal("0.00")

    class Config:
        from_attributes = True

class SubtaskResponse(BaseModel):
    id: int
    project_id: int
    subtask_name: str
    alias: str
    short_code: str
    line_item: int
    budget_category: str
    category_amount: Decimal

    class Config:
        from_attributes = True

#-----------------------------------------------------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    wo_date: str
    project_name: str
    wo_number: str
    bmcd_number: str
    total_labor_amount: Decimal = Decimal("0.00")
    total_expenses_amount: Decimal = Decimal("0.00")
    total_travel_amount: Decimal = Decimal("0.00")
    total_tier_fee: Decimal = Decimal("0.00")
    total_budget_amount: Decimal = Decimal("0.00")
    subtasks: Optional[List[SubtaskCreate]] = []

    class Config:
        from_attributes = True

class ProjectResponse(BaseModel):
    id: int
    wo_date: str
    project_name: str
    wo_number: str
    bmcd_number: str
    total_labor_amount: Decimal = Decimal("0.00")
    total_expenses_amount: Decimal = Decimal("0.00")
    total_travel_amount: Decimal = Decimal("0.00")
    total_tier_fee: Decimal = Decimal("0.00")
    total_budget_amount: Decimal = Decimal("0.00")
    subtasks: List[SubtaskResponse] = []

    class Config:
        from_attributes = True

#-----------------------------------------------------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    invoice_percentage: Decimal
    tier_fee_percentage: Decimal
    invoice_through_date: str

    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    subtask_id: int
    tier_fee_percentage: Decimal
    invoice_percentage: Decimal
    invoice_amount: Decimal
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
    invoice_amount: Decimal
    invoice_number: str
    invoice_percentage: Decimal
    tier_fee_percentage: Decimal
    invoice_through_date: str
    invoice_creation_date: str

    class Config:
        from_attributes = True