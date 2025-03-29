from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from backend.database import MainBase, MainEngine
from backend.routers import projects, invoices, upload

app = FastAPI()

# CORS - only needed if you use JS clients or HTMX from another origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# Create the DB on startup
MainBase.metadata.create_all(bind=MainEngine)

# Optional: Redirect root to project list
@app.get("/", response_class=HTMLResponse)
def redirect_to_projects(request: Request):
    return templates.TemplateResponse("redirect.html", {
        "request": request,
        "redirect_url": "/projects/"
    })

# Backend routers
app.include_router(upload.router)
app.include_router(projects.router)
app.include_router(invoices.router)

