from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from backend.database import get_main_db
from backend import models

router = APIRouter(prefix="/projects", tags=["Projects"])
templates = Jinja2Templates(directory="frontend/templates")


# 🔹 Render all projects
@router.get("/", response_class=HTMLResponse)
def list_projects(request: Request, db: Session = Depends(get_main_db)):
    projects = db.query(models.Project).all()
    return templates.TemplateResponse("index.html", {"request": request, "projects": projects})

# 🔹 Return project card (used by HTMX create)
@router.get("/{project_id}", response_class=HTMLResponse)
def view_project(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Sort subtasks by name, then category
    project.subtasks.sort(key=lambda s: (s.subtask_name.lower(), s.budget_category.lower()))

    return templates.TemplateResponse("project_detail.html", {"request": request, "project": project})

# 🔹 Show create form (if needed)
@router.get("/create-form", response_class=HTMLResponse)
def show_create_form(request: Request):
    return templates.TemplateResponse("components/project_form.html", {"request": request})

# 🔹 Create new project
@router.post("/create", response_class=HTMLResponse)
async def create_project(
    request: Request,
    db: Session = Depends(get_main_db),
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
    return templates.TemplateResponse("components/project_row.html", {"request": request, "project": new_project})

# 🔹 Show edit form (pre-filled)
@router.get("/{project_id}/edit", response_class=HTMLResponse)
def show_edit_form(project_id: int, request: Request, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse("components/project_form.html", {"request": request, "project": project})

# 🔹 Update project
@router.post("/{project_id}/update", response_class=HTMLResponse)
async def update_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_main_db),
    project_name: str = Form(...),
    wo_number: str = Form(...),
    wo_date: str = Form(...),
    bmcd_number: str = Form(""),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.project_name = project_name
    project.wo_number = wo_number
    project.wo_date = wo_date
    project.bmcd_number = bmcd_number

    db.commit()
    db.refresh(project)

    return templates.TemplateResponse("components/project_card.html", {"request": request, "project": project})

# 🔹 Delete project
@router.delete("/{project_id}", response_class=HTMLResponse)
def delete_project(project_id: int, db: Session = Depends(get_main_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

    return HTMLResponse(content="")  # HTMX will remove the card from the DOM
