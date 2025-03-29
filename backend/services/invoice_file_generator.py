from sqlalchemy.orm import Session
from backend.database import MainSessionLocal
from backend.models import Project, Subtask, Invoice
import io
from openpyxl import load_workbook
import tempfile
import pythoncom
import win32com.client
from datetime import datetime
import re

def generate_invoice_excel_bytes(project_id: int, invoice_number: str, template_path: str) -> bytes:
    db: Session = MainSessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise Exception("Project not found")

        invoice = (
            db.query(Invoice)
            .join(Subtask)
            .filter(Invoice.invoice_number == invoice_number)
            .order_by(Invoice.id.desc())
            .first()
        )
        if not invoice:
            raise Exception("No invoice found for project")

        invoice_number = invoice.invoice_number

        match = re.match(r"(.+)-(\d+)", invoice_number)
        if match:
            base_number, current_suffix = match.groups()
            prev_suffix = int(current_suffix) - 1
            previous_invoice_number = f"{base_number}-{prev_suffix}" if prev_suffix > 0 else None
        else:
            previous_invoice_number = None

        # Get previous invoice total
        prev_invoice_total = 0.0
        if previous_invoice_number:
            prev_invoices = db.query(Invoice).filter(Invoice.invoice_number == previous_invoice_number).all()
            prev_invoice_total = round(sum(inv.invoice_amount for inv in prev_invoices), 2)

        wb = load_workbook(template_path)
        ws = wb.active

        # Header
        ws["K48"] = prev_invoice_total
        ws["C3"] = project.bmcd_number
        ws["C4"] = invoice_number
        ws["C5"] = project.contract_number
        ws["C6"] = project.po_number
        ws["C7"] = f"{project.tao_number}-{project.po_number}"
        ws["C8"] = project.wo_number
        ws["C9"] = project.project_name
        ws["C10"] = project.total_budget_amount

        def generate_cell_map():
            base_row_map = {
                "labor": 15,
                "fee": 16,
                "non-travel expenses": 17,
                "travel expenses": 18,
            }
            cell_map = {}

            for subtask_name, row_offset in [("Scoping", 0), ("Physical", 7), ("P&C", 14), ("Telecom", 21)]:
                for category, base_row in base_row_map.items():
                    row = base_row + row_offset
                    cell_map[(subtask_name, category)] = (f"H{row}", f"K{row}")

            return cell_map

        subtasks_invoices = (
            db.query(Subtask, Invoice)
            .join(Invoice)
            .filter(Invoice.invoice_number == invoice_number)
            .all()
        )

        formatted_date = datetime.strptime(invoice.invoice_through_date, "%Y-%m-%d").strftime("%d-%b-%y")
        ws["J3"] = formatted_date

        cell_map = generate_cell_map()

        for subtask, invoice in subtasks_invoices:
            key = (subtask.subtask_name, subtask.budget_category.strip().lower())
            if key in cell_map:
                cell_line_item, cell_amount = cell_map[key]
                ws[cell_line_item] = subtask.line_item
                ws[cell_amount] = invoice.invoice_amount

        # Save to memory
        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)
        return file_stream.read()

    finally:
        db.close()

def generate_invoice_pdf_bytes(project_id: int, invoice_number: str, template_path: str) -> bytes:
    # Step 1: Generate Excel bytes in memory
    excel_bytes = generate_invoice_excel_bytes(project_id, invoice_number, template_path)

    # Step 2: Write Excel to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
        tmp_excel.write(excel_bytes)
        tmp_excel_path = tmp_excel.name

    tmp_pdf_path = tmp_excel_path.replace(".xlsx", ".pdf")

    # Step 3: Use COM to convert to PDF
    pythoncom.CoInitialize()
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    wb = excel.Workbooks.Open(tmp_excel_path)
    wb.ExportAsFixedFormat(0, tmp_pdf_path)  # 0 = PDF format
    wb.Close(False)
    excel.Quit()
    pythoncom.CoUninitialize()

    # Step 4: Read PDF and return bytes
    with open(tmp_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    return pdf_bytes
