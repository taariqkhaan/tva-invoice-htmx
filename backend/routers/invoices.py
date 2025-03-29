import os
import io
from fastapi import APIRouter, Depends, HTTPException, Response, Path, Request, Form
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from fastapi.templating import Jinja2Templates
from backend import models
from backend.schemas import InvoiceCreate,InvoiceResponse
from backend.database import get_main_db
from backend.services.invoicing_logic import generate_invoice
from backend.services.invoice_file_generator import generate_invoice_excel_bytes, generate_invoice_pdf_bytes


router = APIRouter(tags=["Invoices"])
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/invoices", response_class=HTMLResponse)
def get_all_invoices(request: Request, db: Session = Depends(get_main_db)):
    invoices = (
        db.query(
            models.Project.project_name,
            models.Project.wo_number,
            models.Project.bmcd_number,
            models.Project.id,
        )
        .all()
    )
    return templates.TemplateResponse("invoices.html", {
        "request": request,
        "invoices": invoices
    })

@router.get("/invoices/view/{project_id}", response_class=HTMLResponse)
def view_project_invoices_modal(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    invoices = project.invoices
    return templates.TemplateResponse("components/invoice_list.html", {
        "request": request,
        "project": project,
        "invoices": invoices
    })

@router.get("/invoices/create/{project_id}", response_class=HTMLResponse)
def get_invoice_form(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return templates.TemplateResponse("components/invoice_form.html", {
        "request": request,
        "project": project
    })



@router.post("/invoices/create/{project_id}", response_class=HTMLResponse)
def create_invoice(
    request: Request,
    project_id: int,
    invoice_percentage: float = Form(...),
    tier_fee_percentage: float = Form(...),
    invoice_through_date: str = Form(...),
    db: Session = Depends(get_main_db)
):
    try:
        invoice = generate_invoice(
            db=db,
            project_id=project_id,
            invoice_percentage=invoice_percentage,
            tier_fee_percentage=tier_fee_percentage,
            invoice_through_date=invoice_through_date
        )

        # Redirect back to the invoice list modal or page
        return RedirectResponse(
            url=f"/invoices/view/{project_id}",
            status_code=303
        )

    except ValueError as e:
        return templates.TemplateResponse("components/invoice_form.html", {
            "request": request,
            "error": str(e),
            "project_id": project_id
        })






@router.get("/download_invoice/{invoice_number}")
def download_invoice(project_id: int, invoice_number: str):
    try:
        template_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                     "..", "files", "tva_invoice_template.xlsx"))
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
def download_invoice_pdf(project_id: int, invoice_number: str):
    try:
        template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files", "tva_invoice_template.xlsx"))
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

@router.delete("/invoices/{invoice_number}", status_code=204)
def delete_invoice(
    project_id: int,
    invoice_number: str = Path(...),
    db: Session = Depends(get_main_db)
):
    # Get all subtasks for the project
    subtasks = db.query(models.Subtask).filter(models.Subtask.project_id == project_id).all()
    subtask_ids = [s.id for s in subtasks]

    # Delete all matching invoice records with that invoice_number
    result = db.query(models.Invoice).filter(
        models.Invoice.subtask_id.in_(subtask_ids),
        models.Invoice.invoice_number == invoice_number
    ).delete(synchronize_session=False)

    if result == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    db.commit()
    return Response(status_code=204)