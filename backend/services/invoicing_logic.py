from sqlalchemy.orm import Session
from backend.models import Project, Subtask, Invoice, InvoiceAmount
from datetime import date
import re

def generate_invoice(
    db: Session,
    project_id: int,
    invoice_percentage: float,
    tier_fee_percentage: float,
    invoice_through_date: str
):
    # Step 1: Get project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found.")

    # Step 2: Get subtasks
    subtasks = db.query(Subtask).filter(Subtask.project_id == project_id).all()
    if not subtasks:
        raise ValueError("No subtasks found for this project.")

    # Step 3: Determine next invoice number (based on project.bmcd_number)
    existing_invoice_numbers = (
        db.query(Invoice.invoice_number)
        .filter(Invoice.project_id == project_id)
        .all()
    )

    suffixes = []
    pattern = re.compile(rf"^{project.bmcd_number}-(\d+)$")
    for (inv_num,) in existing_invoice_numbers:
        match = pattern.match(inv_num)
        if match:
            suffixes.append(int(match.group(1)))

    next_suffix = max(suffixes, default=0) + 1
    invoice_number = f"{project.bmcd_number}-{next_suffix}"

    # Step 4: Determine max previous percentage for this project
    max_previous_percentage = (
        db.query(Invoice.invoice_percentage)
        .filter(Invoice.project_id == project_id)
        .order_by(Invoice.invoice_percentage.desc())
        .first()
    )
    previous_max = max_previous_percentage[0] if max_previous_percentage else 0.0

    delta_percentage = invoice_percentage - previous_max
    if delta_percentage <= 0:
        raise ValueError("Invoice percentage must be greater than previous maximum.")

    if invoice_percentage > 100:
        raise ValueError("Invoice percentage cannot exceed 100%.")

    percent = delta_percentage / 100.0
    tier_percent = tier_fee_percentage / 100.0

    # Step 5: Create invoice + invoice amount entries
    new_invoice = Invoice(
        project_id=project_id,
        tier_fee_percentage=tier_fee_percentage,
        invoice_percentage=invoice_percentage,
        invoice_number=invoice_number,
        invoice_through_date=invoice_through_date,
        invoice_creation_date=date.today().isoformat(),
    )
    db.add(new_invoice)
    db.flush()  # So new_invoice.id is available

    created_amounts = []
    for subtask in subtasks:
        amount = subtask.category_amount or 0.0

        if subtask.budget_category.strip().lower() == "fee":
            invoice_amount_value = amount * percent * tier_percent
        else:
            invoice_amount_value = amount * percent

        inv_amt = InvoiceAmount(
            invoice_id=new_invoice.id,
            subtask_id=subtask.id,
            invoice_amount=round(invoice_amount_value, 2),
        )
        db.add(inv_amt)
        created_amounts.append(inv_amt)

    db.commit()
    return created_amounts
