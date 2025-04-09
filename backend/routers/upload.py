import os
from io import BytesIO
from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from backend.database import PdfBase, PdfEngine, PdfSessionLocal, MainSessionLocal
from backend.services.pdf_to_db import extract_pdf_to_db
from backend.services.po_tao_logic import create_project_from_files
from backend.services.assign_tags import assign_tao_tags, assign_po_tags, check_docs

router = APIRouter(prefix="/projects", tags=["Upload"])
templates = Jinja2Templates(directory="frontend/templates")

# GET: Show upload form
@router.get("/upload-po-tao", response_class=HTMLResponse)
def show_upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


# POST: Upload and process PDF files
@router.post("/upload-po-tao")
async def upload_po_tao(
    request: Request,
    po_file: UploadFile = File(...),
    tao_file: UploadFile = File(...),
    form_number: str = Form(...)
):
    is_htmx = request.headers.get("hx-request") == "true"

    try:
        temp_db_path = "./temp_data.db"
        PdfEngine.dispose()

        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

        PdfBase.metadata.create_all(bind=PdfEngine)
        pdf_db = PdfSessionLocal()
    except Exception as e:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "error": f"Initialization error: {str(e)}"
        })

    try:
        po_data = await po_file.read()
        tao_data = await tao_file.read()

        extract_pdf_to_db(BytesIO(po_data), "po_table", pdf_db)
        extract_pdf_to_db(BytesIO(tao_data), "tao_table", pdf_db)
        assign_tao_tags(pdf_db)
        assign_po_tags(pdf_db)
        check_result = check_docs(pdf_db)

        validation_status = check_result["validation_status"]
        validation_message = check_result["validation_message"]

        if validation_status == "success":
            with MainSessionLocal() as main_db:
                create_project_from_files(pdf_db, main_db, form_number)
                pdf_db.commit()
                response = templates.TemplateResponse("components/upload_modal_content.html", {
                    "request": request,
                })
                response.headers["HX-Trigger"] = "FilesUploaded"
                return response

    except Exception as e:
        pdf_db.rollback()
        context = {
            "request": request,
            "error": f"Processing error: {str(e)}"
        }
        if is_htmx:
            return templates.TemplateResponse("components/upload_modal_content.html", context)
        return templates.TemplateResponse("upload.html", context)
    finally:
        pdf_db.close()


