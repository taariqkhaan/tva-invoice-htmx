import os
import io
from fastapi import APIRouter, Depends, HTTPException, Response, Path, Request, Form
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from decimal import Decimal, InvalidOperation
from fastapi.templating import Jinja2Templates
from backend.models import Project, Invoice
from backend import models
from backend.schemas import InvoiceCreate,InvoiceResponse
from backend.database import get_main_db
from backend.services.invoicing_logic import generate_invoice
from backend.services.invoice_file_generator import generate_invoice_excel_bytes, generate_invoice_pdf_bytes


router = APIRouter(tags=["Invoices"])
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/invoices/{project_id}", response_class=HTMLResponse)
def view_project_invoices_page(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    invoices = project.invoices

    # Budget from project
    total_budget = project.total_budget_amount

    # Sum amounts per invoice
    invoice_data = []
    total_invoiced = Decimal("0.00")
    for invoice in invoices:
        total_amount = sum((item.invoice_amount for item in invoice.invoice_items), Decimal("0.00"))
        total_invoiced += total_amount

        formatted_through_date = datetime.strptime(invoice.invoice_through_date, "%Y-%m-%d").strftime("%m/%d/%Y")
        invoice_data.append({
            "invoice": invoice,
            "total_amount": total_amount,
            "formatted_through_date": formatted_through_date
        })

    contributions = [
        {
            "number": row["invoice"].invoice_number,
            "percent": (row["total_amount"] / project.total_budget_amount * Decimal("100")).quantize(Decimal("0.01")),
            "amount": row["total_amount"]
        }
        for row in invoice_data
    ]

    return templates.TemplateResponse("invoice_list.html", {
        "request": request,
        "project": project,
        "invoices": invoice_data,
        "total_invoiced": total_invoiced,
        "total_budget": total_budget,
        "contributions": contributions
    })

@router.get("/invoices/create/{project_id}", response_class=HTMLResponse)
def get_invoice_form(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Budget check
    if not project.total_budget_amount or project.total_budget_amount <= 0:
        return templates.TemplateResponse("components/error_modal.html", {
            "request": request,
            "message": "Total approved amount is $0. "
                       "Please update the project's approved budget before creating an invoice."
        })

    latest_invoice = (
        db.query(Invoice)
        .filter(Invoice.project_id == project_id)
        .order_by(Invoice.invoice_percentage.desc())
        .first()
    )

    last_percentage = latest_invoice.invoice_percentage if latest_invoice else Decimal("0.00")

    # Check if 100% of approved amount is invoiced
    if last_percentage.quantize(Decimal("0.01")) >= Decimal("100.00"):
        return templates.TemplateResponse("components/error_modal.html", {
            "request": request,
            "message": "All approved amount has been invoiced."
        })

    is_first_invoice = latest_invoice is None
    existing_tier_fee = latest_invoice.tier_fee_percentage if latest_invoice else None

    return templates.TemplateResponse("components/invoice_create.html", {
        "request": request,
        "project": project,
        "last_percentage": last_percentage,
        "is_first_invoice": is_first_invoice,
        "existing_tier_fee": existing_tier_fee
    })

@router.get("/invoices/details/{invoice_number}", response_class=HTMLResponse)
def view_invoice_details(invoice_number: str, request: Request, db: Session = Depends(get_main_db)):
    from backend.models import Invoice, Project, InvoiceAmount, Subtask

    # Step 1: Fetch the invoice
    invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    formatted_through_date = datetime.strptime(invoice.invoice_through_date, "%Y-%m-%d").strftime("%m/%d/%Y")
    formatted_creation_date = datetime.strptime(invoice.invoice_creation_date, "%Y-%m-%d").strftime("%m/%d/%Y")

    # Step 2: Fetch project
    project = db.query(Project).filter(Project.id == invoice.project_id).first()

    # Step 3: Fetch invoice amounts
    invoice_amounts = db.query(InvoiceAmount).filter(InvoiceAmount.invoice_id == invoice.id).all()

    # Step 4: Get all related subtasks (via subtask_id in InvoiceAmount)
    subtask_ids = [item.subtask_id for item in invoice_amounts]
    subtasks = db.query(Subtask).filter(Subtask.id.in_(subtask_ids)).all()
    subtask_lookup = {sub.id: sub for sub in subtasks}

    # Combine invoice_amount with its subtask for sorting
    combined = [
        (subtask_lookup[item.subtask_id], item)
        for item in invoice_amounts
        if item.subtask_id in subtask_lookup
    ]

    # Sort by subtask name, then by budget category
    sorted_combined = sorted(
        combined,
        key=lambda pair: (
            pair[0].subtask_name.lower(),
            pair[0].budget_category.lower()
        )
    )

    return templates.TemplateResponse("components/invoice_details.html", {
        "request": request,
        "invoice": invoice,
        "project": project,
        "subtask_items": sorted_combined,
        "formatted_through_date": formatted_through_date,
        "formatted_creation_date": formatted_creation_date
    })

@router.get("/invoices/download-options/{invoice_number}", response_class=HTMLResponse)
def download_invoice_modal(invoice_number: str, project_id: int, request: Request, db: Session = Depends(get_main_db)):
    return templates.TemplateResponse("components/invoice_download.html", {
        "request": request,
        "invoice_number": invoice_number,
        "project_id": project_id
    })

@router.get("/download_invoice_excel/{invoice_number}")
def download_invoice_excel(invoice_number: str, project_id: int):
    try:
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        template_path = os.path.join(PROJECT_ROOT, "files", "tva_invoice_template.xlsx")


        file_bytes = generate_invoice_excel_bytes(project_id, invoice_number, template_path)

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={invoice_number}.xlsx"
            }
        )
    except Exception as e:
        return Response(content=f"Error generating invoice: {e}", status_code=500)

@router.get("/download_invoice_pdf/{invoice_number}")
def download_invoice_pdf(invoice_number: str, project_id: int):
    try:
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        template_path = os.path.join(PROJECT_ROOT, "files", "tva_invoice_template.xlsx")

        pdf_bytes = generate_invoice_pdf_bytes(project_id, invoice_number, template_path)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{invoice_number}.pdf"'
            }
        )
    except Exception as e:
        return Response(content=f"Error generating PDF invoice: {e}", status_code=500)


@router.post("/invoices/create/{project_id}", response_class=HTMLResponse)
def create_invoice(
    request: Request,
    project_id: int,
    invoice_percentage: str = Form(...),
    tier_fee_percentage: str = Form(...),
    invoice_through_date: str = Form(...),
    db: Session = Depends(get_main_db)
):

    try:

        # Parse submitted date
        submitted_date = datetime.strptime(invoice_through_date, "%Y-%m-%d")

        # Get latest invoice (if any)
        latest_invoice = (
            db.query(Invoice)
            .filter(Invoice.project_id == project_id)
            .order_by(Invoice.invoice_percentage.desc())
            .first()
        )

        # Validate date order
        if latest_invoice:
            latest_date = datetime.strptime(latest_invoice.invoice_through_date, "%Y-%m-%d")
            if submitted_date <= latest_date:
                project = db.query(Project).filter(Project.id == project_id).first()
                return templates.TemplateResponse("components/invoice_create.html", {
                    "request": request,
                    "project": project,
                    "last_percentage": latest_invoice.invoice_percentage,
                    "is_first_invoice": False,
                    "existing_tier_fee": latest_invoice.tier_fee_percentage,
                    "date_error": f"Invoice date must be after the last invoice's date ({latest_date.strftime('%m/%d/%Y')})."
                })

        invoice_percentage = Decimal(invoice_percentage)
        tier_fee_percentage = Decimal(tier_fee_percentage)

        invoice = generate_invoice(
            db=db,
            project_id=project_id,
            invoice_percentage=invoice_percentage,
            tier_fee_percentage=tier_fee_percentage,
            invoice_through_date=invoice_through_date
        )

        # Rebuild invoice data
        project = db.query(Project).filter(Project.id == project_id).first()
        invoices = project.invoices

        invoice_data = []
        total_invoiced = Decimal("0.00")
        for invoice in invoices:
            total_amount = sum(
                (item.invoice_amount for item in invoice.invoice_items),
                Decimal("0.00")
            )
            total_invoiced += total_amount
            formatted_through_date = datetime.strptime(
                invoice.invoice_through_date, "%Y-%m-%d"
            ).strftime("%m/%d/%Y")

            invoice_data.append({
                "invoice": invoice,
                "total_amount": total_amount,
                "formatted_through_date": formatted_through_date
            })

        response = templates.TemplateResponse("components/invoice_row.html", {
            "request": request,
            "invoices": invoice_data
        })
        response.headers["HX-Trigger"] = "invoiceCreated"
        return response

    except ValueError as e:
        project = db.query(Project).filter(Project.id == project_id).first()
        return templates.TemplateResponse("components/invoice_create.html", {
            "request": request,
            "error": str(e),
            "project": project
        })



@router.post("/invoices/delete/{invoice_number}")
def delete_invoice(invoice_number: str, db: Session = Depends(get_main_db)):
    invoice = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    project_id = invoice.project_id  # optional if you want to redirect back to the project page

    db.delete(invoice)
    db.commit()

    return RedirectResponse(url=f"/invoices/{project_id}", status_code=303)


