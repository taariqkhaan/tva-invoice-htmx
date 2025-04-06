from fastapi import APIRouter, Depends, Request, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from backend.database import get_main_db, MainEngine
from backend import models
from backend.models import Project, InvoiceAmount
from backend.schemas import ProjectCreate, SubtaskCreate
from backend.services.blank_project_calc import calculate_totals
from datetime import datetime

router = APIRouter(prefix="/projects", tags=["Projects"])
templates = Jinja2Templates(directory="frontend/templates")

#==============================================GET======================================================================

# Get default values to create a blank project
@router.get("/create-blank", response_class=HTMLResponse)
def show_blank_project(request: Request):
    from backend.schemas import SubtaskCreate

    default_subtasks = []
    disciplines = [
        ("Physical", "M2"),
        ("P&C", "N1"),
        ("Telecom", "T1"),
        ("Scoping", "B9")
    ]
    budget_categories = ["Labor", "Fee", "Non-Travel Expenses", "Travel Expenses"]

    for discipline_name, alias in disciplines:
        for category in budget_categories:
            default_subtasks.append(SubtaskCreate(
                subtask_name=discipline_name,
                alias=alias,
                short_code="NA",
                line_item=0,
                budget_category=category
            ))

    default_project = {
        "id": 0,
        "project_name": "NA",
        "wo_number": "NA",
        "wo_date": "",
        "bmcd_number": "000000",
        "po_number": "NA",
        "tao_number": "NA",
        "contract_number": "NA",
        "subtasks": default_subtasks
    }

    return templates.TemplateResponse("components/project_edit.html", {
        "request": request,
        "project": default_project,
        "is_new": True
    })

# Get all projects
@router.get("/", response_class=HTMLResponse)
def list_projects(request: Request, db: Session = Depends(get_main_db), page: int = 1, limit: int = 33):

    offset = (page - 1) * limit
    total_projects = db.query(models.Project).count()
    projects = db.query(models.Project).offset(offset).limit(limit).all()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "projects": projects,
        "page": page,
        "limit": limit,
        "total_projects": total_projects,
        "total_pages": (total_projects + limit - 1) // limit
    })

# Get project details
@router.get("/{project_id}", response_class=HTMLResponse)
def view_project(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all invoice amounts for subtasks in this project
    subtask_ids = [sub.id for sub in project.subtasks]

    invoice_amounts = (
        db.query(InvoiceAmount.subtask_id, func.sum(InvoiceAmount.invoice_amount))
        .filter(InvoiceAmount.subtask_id.in_(subtask_ids))
        .group_by(InvoiceAmount.subtask_id)
        .all()
    )

    # Build a lookup: subtask_id → total invoiced amount
    invoiced_lookup = {sub_id: total or 0.0 for sub_id, total in invoice_amounts}

    # Sort subtasks by name, then category
    project.subtasks.sort(key=lambda s: (s.subtask_name.lower(), s.budget_category.lower()))

    return templates.TemplateResponse("project_details.html",
                                      {"request": request,
                                       "project": project,
                                       "invoiced_lookup": invoiced_lookup
                                       })


# Get existing project data to edit project
@router.get("/{project_id}/edit", response_class=HTMLResponse)
def show_full_edit_modal(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.invoices and len(project.invoices) > 0:
        return templates.TemplateResponse("components/error_modal.html", {
            "request": request,
            "message": "Editing project will cause data mismatch in existing invoices."
                       " Please delete all existing invoices to proceed."
        })

    return templates.TemplateResponse("components/project_edit.html", {
        "request": request,
        "project": project,
        "is_new": False
    })

#=======================================================================================================================



#==============================================POST=====================================================================

# Create new project from files
@router.post("/create", response_class=HTMLResponse)
async def create_project(request: Request, db: Session = Depends(get_main_db),
    project_name: str = Form(...),
    wo_number: str = Form(...),
    wo_date: str = Form(...),
    bmcd_number: str = Form(""),
):
    new_project = models.Project(
        project_name=project_name,
        wo_number=wo_number,
        wo_date=wo_date,
        bmcd_number=bmcd_number,
        total_labor_amount=0.0,
        total_expenses_amount=0.0,
        total_travel_amount=0.0,
        total_tier_fee=0.0,
        total_budget_amount=0.0
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return templates.TemplateResponse("components/project_list.html", {"request": request, "project": new_project})

# Create new blank project
@router.post("/create-blank", response_class=HTMLResponse)
async def create_blank_project(request: Request, db: Session = Depends(get_main_db),
    project_name: str = Form(...),
    wo_number: str = Form(...),
    wo_date: str = Form(...),
    bmcd_number: str = Form(...),
    po_number: str = Form(...),
    tao_number: str = Form(...),
    contract_number: str = Form(...),
    subtask_name: list[str] = Form(default=[]),
    alias: list[str] = Form(default=[]),
    short_code: list[str] = Form(default=[]),
    line_item: list[int] = Form(default=[]),
    budget_category: list[str] = Form(default=[]),
    category_amount: list[float] = Form(default=[]),
):
    totals = calculate_totals(budget_category, category_amount)

    new_project = models.Project(
        project_name=project_name,
        wo_number=wo_number,
        wo_date=wo_date,
        bmcd_number=bmcd_number,
        po_number=po_number,
        tao_number=tao_number,
        contract_number=contract_number,
        total_labor_amount=totals["labor"],
        total_tier_fee=totals["fee"],
        total_expenses_amount=totals["expenses"],
        total_travel_amount=totals["travel"],
        total_budget_amount=totals["budget"]
    )

    db.add(new_project)
    db.flush()

    for i in range(len(subtask_name)):
        sub = models.Subtask(
            subtask_name=subtask_name[i],
            alias=alias[i],
            short_code=short_code[i],
            line_item=line_item[i],
            budget_category=budget_category[i],
            category_amount=category_amount[i],
            project=new_project
        )
        db.add(sub)

    db.commit()
    db.refresh(new_project)

    return templates.TemplateResponse("components/project_list.html", {
        "request": request,
        "project": new_project
    })

#=======================================================================================================================



#==============================================DELETE===================================================================

# Delete project
@router.delete("/{project_id}", response_class=HTMLResponse)
def delete_project(project_id: int, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

    with MainEngine.connect() as conn:
        conn.execute(text("VACUUM"))

    return HTMLResponse(content="")

#=======================================================================================================================



