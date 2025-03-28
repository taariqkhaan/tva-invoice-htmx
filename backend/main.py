from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, status, Form, Path, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy.orm import Session
from typing import List
from io import BytesIO
import os
import io
import re
import models
import schemas
from schemas import InvoiceCreate,InvoiceResponse, ProjectInvoiceResponse
from main_database import MainEngine, MainBase, get_main_db, MainSessionLocal
from pdf_database import PdfEngine, PdfBase, PdfSessionLocal
from pdf_to_db import extract_pdf_to_db
from po_tao_logic import create_project_from_files
import assign_tags
from invoicing_logic import generate_invoice
from invoice_file_generator import generate_invoice_excel_bytes, generate_invoice_pdf_bytes


# Initialize FastAPI app
app = FastAPI()

# Define allowed origins for CORS
origins = ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the database tables defined in models
MainBase.metadata.create_all(bind=MainEngine)


templates = Jinja2Templates(directory="templates")

@app.get("/frontend", response_class=HTMLResponse)
async def frontend(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/projects/htmx", response_class=HTMLResponse)
def htmx_projects(request: Request, db: Session = Depends(get_main_db)):
    projects = db.query(models.Project).all()
    return templates.TemplateResponse("/project_table.html", {
        "request": request,
        "projects": projects
    })


# Default
@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>FastAPI is running</h1>"

# Fetch all projects
@app.get("/projects/", response_model=List[schemas.ProjectResponse])
def get_projects(db: Session = Depends(get_main_db)):
    projects = db.query(models.Project).all()
    return projects

# Fetch all subtasks of all projects
@app.get("/projects/{project_id}", response_model=schemas.ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    return project

@app.put("/projects/{project_id}", response_model=schemas.ProjectResponse)
def update_project(project_id: int, project_data: schemas.ProjectCreate, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update the main project fields
    project.wo_date = project_data.wo_date
    project.project_name = project_data.project_name
    project.wo_number = project_data.wo_number
    project.bmcd_number = project_data.bmcd_number

    # --- Recalculate financial totals from subtasks ---
    total_labor = 0.0
    total_expenses = 0.0
    total_travel = 0.0
    total_fee = 0.0

    for sub in project_data.subtasks:
        amount = float(sub.category_amount)
        category = sub.budget_category

        if category == "Labor":
            total_labor += amount
        elif category == "Non-Travel Expenses":
            total_expenses += amount
        elif category == "Travel Expenses":
            total_travel += amount
        elif category == "Fee":
            total_fee += amount

    project.total_labor_amount = total_labor
    project.total_expenses_amount = total_expenses
    project.total_travel_amount = total_travel
    project.total_tier_fee = total_fee
    project.total_budget_amount = total_labor + total_expenses + total_travel + total_fee

    # --- Replace all current subtasks ---
    db.query(models.Subtask).filter(models.Subtask.project_id == project_id).delete()

    new_subtasks = [
        models.Subtask(
            project_id=project_id,
            subtask_name=sub.subtask_name,
            alias=sub.alias,
            short_code=sub.short_code,
            line_item=sub.line_item,
            budget_category=sub.budget_category,
            category_amount=sub.category_amount
        )
        for sub in project_data.subtasks
    ]

    db.add_all(new_subtasks)
    db.commit()
    db.refresh(project)
    return project

@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all subtasks first due to foreign key constraints
    db.query(models.Subtask).filter(models.Subtask.project_id == project_id).delete()

    # Delete the project
    db.delete(project)
    db.commit()

@app.post("/projects/", response_model=schemas.ProjectResponse)
def create_project(project_data: schemas.ProjectCreate, db: Session = Depends(get_main_db)):
        new_project = models.Project(
            wo_date=project_data.wo_date,
            project_name=project_data.project_name,
            wo_number=project_data.wo_number,
            bmcd_number=project_data.bmcd_number,
            total_labor_amount=project_data.total_labor_amount,
            total_expenses_amount=project_data.total_expenses_amount,
            total_travel_amount=project_data.total_travel_amount,
            total_tier_fee=project_data.total_tier_fee,
            total_budget_amount=project_data.total_budget_amount
        )

        db.add(new_project)
        db.flush()

        # Add Subtasks in Bulk
        new_subtasks = [
            models.Subtask(
                project_id=new_project.id,
                subtask_name=subtask.subtask_name,
                alias=subtask.alias,
                short_code=subtask.short_code,
                line_item=subtask.line_item,
                budget_category=subtask.budget_category,
                category_amount=subtask.category_amount
            )
            for subtask in project_data.subtasks
        ]
        db.add_all(new_subtasks)

        db.commit()
        db.refresh(new_project)

        return new_project

@app.post("/projects/upload_po_tao")
async def upload_po_tao(
        po_file: UploadFile = File(...),
        tao_file: UploadFile = File(...),
        form_number: str = Form(...)
):

    try:
        temp_db_path = "./temp_data.db"

        # Step 1: Dispose of current engine to close all connections
        PdfEngine.dispose()

        # Step 2: Delete the SQLite database file
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

        # Step 3: Recreate the tables in a new, empty database
        PdfBase.metadata.create_all(bind=PdfEngine)

        # Step 4: Open a fresh DB session
        pdf_db = PdfSessionLocal()

    except Exception as e:
        return {"status": "error", "message": str(e)}

    po_data = await po_file.read()
    tao_data = await tao_file.read()

    try:
        extract_pdf_to_db(BytesIO(po_data), "po_table", pdf_db)
        extract_pdf_to_db(BytesIO(tao_data), "tao_table", pdf_db)
        assign_tags.assign_tao_tags(pdf_db)
        assign_tags.assign_po_tags(pdf_db)
        check_result = assign_tags.check_docs(pdf_db)
        pdf_db.commit()


        if check_result["validation_status"] == "success":
            with MainSessionLocal() as main_db:
                create_project_from_files(pdf_db, main_db, form_number)


    except Exception as e:
        pdf_db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        pdf_db.close()

    return {
        "status": "processed",
        "validation_status": check_result["validation_status"],
        "validation_message": check_result["validation_message"],
    }

@app.post("/projects/{project_id}/generate_invoice", response_model=List[InvoiceResponse])
def create_invoice(
    project_id: int,
    payload: InvoiceCreate,
    db: Session = Depends(get_main_db)
):
    try:
        invoice = generate_invoice(
            db=db,
            project_id=project_id,
            invoice_percentage=payload.invoice_percentage,
            tier_fee_percentage=payload.tier_fee_percentage,
            invoice_through_date=payload.invoice_through_date
        )
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/projects/{project_id}/invoices", response_model=List[ProjectInvoiceResponse])
def get_project_invoices(project_id: int, db: Session = Depends(get_main_db)):
    # Join Invoices with Subtasks and filter by project_id
    results = (
        db.query(
            models.Subtask.subtask_name,
            models.Subtask.alias,
            models.Subtask.short_code,
            models.Subtask.line_item,
            models.Subtask.budget_category,
            models.Invoice.invoice_amount,
            models.Invoice.invoice_number,
            models.Invoice.invoice_percentage,
            models.Invoice.tier_fee_percentage,
            models.Invoice.invoice_through_date,
            models.Invoice.invoice_creation_date
        )
        .join(models.Invoice, models.Invoice.subtask_id == models.Subtask.id)
        .filter(models.Subtask.project_id == project_id)
        .all()
    )

    # Extract invoice numbers
    invoice_numbers = {r.invoice_number for r in results}

    def extract_suffix(inv_num):
        match = re.search(r"-(\d+)$", str(inv_num))
        return int(match.group(1)) if match else -1

    # Find latest invoice number
    latest_invoice_number = max(invoice_numbers, key=extract_suffix, default=None)

    # Convert result rows to dicts
    invoices = [dict(row._mapping) for row in results]

    return JSONResponse(content={
        "invoices": invoices,
        "latest_invoice_number": latest_invoice_number
    })

@app.get("/projects/{project_id}/download_invoice/{invoice_number}")
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

@app.get("/projects/{project_id}/download_invoice_pdf/{invoice_number}")
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


@app.delete("/projects/{project_id}/invoices/{invoice_number}", status_code=204)
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




#-----------------------------------------------------------------------------------------------------------------------



