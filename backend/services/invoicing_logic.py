from sqlalchemy.orm import Session
from backend.models import Project, Subtask, Invoice
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

    # Step 3: Determine the next invoice number
    existing_invoice_numbers = (
        db.query(Invoice.invoice_number)
        .join(Subtask)
        .filter(Subtask.project_id == project_id)
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

    # Step 4: Get max previously invoiced percentage for this project
    max_previous_percentage = (
        db.query(Invoice.invoice_percentage)
        .join(Subtask)
        .filter(Subtask.project_id == project_id)
        .order_by(Invoice.invoice_percentage.desc())
        .first()
    )
    previous_max = max_previous_percentage[0] if max_previous_percentage else 0.0

    # Calculate the delta
    delta_percentage = invoice_percentage - previous_max
    if delta_percentage <= 0:
        raise ValueError("Invoice percentage must be greater than previous maximum.")

    percent = delta_percentage / 100.0
    tier_percent = tier_fee_percentage / 100.0

    # Step 4: Create invoices
    created_invoices = []
    for subtask in subtasks:
        amount = subtask.category_amount or 0.0

        if subtask.budget_category.strip().lower() == "fee":
            invoice_amount = amount * percent * tier_percent
        else:
            invoice_amount = amount * percent

        invoice = Invoice(
            subtask_id=subtask.id,
            tier_fee_percentage=tier_fee_percentage,
            invoice_percentage=invoice_percentage,
            invoice_amount=round(invoice_amount, 2),
            invoice_number=invoice_number,
            invoice_through_date=invoice_through_date,
            invoice_creation_date=date.today().isoformat()
        )

        db.add(invoice)
        created_invoices.append(invoice)

    db.commit()
    return created_invoices
