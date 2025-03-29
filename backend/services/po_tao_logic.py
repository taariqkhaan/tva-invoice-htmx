from sqlalchemy.orm import Session
from collections import defaultdict
from backend.models import ExtractedWord, Project, Subtask


def get_aggregated_data_from_temp_db(pdf_db: Session, bmcd_form_number: str) -> dict:
    result = pdf_db.query(ExtractedWord).filter(ExtractedWord.word_tag.isnot(None)).all()

    if not result:
        raise Exception("No data found in temp_data.db")

    # Separate rows with and without item_no
    project_level_data = [r for r in result if r.item_no is None]
    item_level_data = [r for r in result if r.item_no is not None]

    # Extract from project-level rows
    wo_number = next((r.word for r in project_level_data if r.word_tag == "wo_num"), None)
    wo_date = next((r.word for r in project_level_data if r.word_tag == "po_appr_date"), None)
    po_number = next((r.word for r in project_level_data if r.word_tag == "po_num"), None)
    tao_number = next((r.word for r in project_level_data if r.word_tag == "tao_num"), None)
    contract_number = next((r.word for r in project_level_data if r.word_tag == "contract_num"), None)

    # Extract Project Name (PO Description)
    po_desc_words = [r for r in project_level_data if r.word_tag == "po_desc"]
    sorted_po_desc = sorted(po_desc_words, key=lambda x: x.id)
    project_name = " ".join(w.word for w in sorted_po_desc).strip()

    # Group item-level words by item_no
    items_by_number = {}
    for row in item_level_data:
        items_by_number.setdefault(row.item_no, []).append(row)

    # Alias → Subtask Name mapping
    alias_to_name = {
        "M2": "Physical",
        "N1": "P&C",
        "B9": "Scoping",
        "T1": "Telecom"
    }

    # Alias → short code map
    short_code_map = {}
    short_code_rows = [r for r in result if r.word_tag in ("short_alias", "short_code")]
    sorted_rows = sorted(short_code_rows, key=lambda x: x.id)

    for i in range(len(sorted_rows) - 1):
        current_row = sorted_rows[i]
        next_row = sorted_rows[i + 1]

        if current_row.word_tag == "short_alias" and next_row.word_tag == "short_code":
            cleaned_alias = current_row.word.strip().strip("()")
            short_code_map[cleaned_alias] = next_row.word.strip()

    subtasks = []

    for item_no, words in items_by_number.items():
        subtask = {
            "line_item": None,
            "alias": None,
            "subtask_name": None,
            "short_code": None,
            "budget_category": "",
            "category_amount": 0.0
        }

        for word in words:
            if word.word_tag == "line_no":
                try:
                    subtask["line_item"] = int(word.word.strip())
                except:
                    subtask["line_item"] = None
            elif word.word_tag == "alias":
                raw_alias = word.word.strip()
                cleaned_alias = raw_alias.strip("()")
                subtask["alias"] = cleaned_alias
                subtask["subtask_name"] = alias_to_name.get(cleaned_alias, "N/A")
                subtask["short_code"] = short_code_map.get(cleaned_alias, "")
            elif word.word_tag == "cost_type":
                cost_type_val = word.word.strip().title()
                if cost_type_val.lower() == "travel":
                    cost_type_val = "Travel Expenses"

                if cost_type_val.lower() == "non-travel":
                    cost_type_val = "Non-Travel Expenses"

                if cost_type_val.lower() != "expenses":
                    subtask["budget_category"] = cost_type_val

            elif word.word_tag == "line_cost":
                try:
                    subtask["category_amount"] = float(word.word.replace(",", "").replace("$", "").strip())
                except ValueError:
                    subtask["category_amount"] = 0.0

        # Only add if alias is found
        if subtask["alias"]:
            subtasks.append(subtask)

    # After all subtasks are parsed, ensure all aliases and budget categories are present
    existing_alias_budget_pairs = {(sub["alias"], sub["budget_category"]) for sub in subtasks}

    for alias, name in alias_to_name.items():
        for budget_category in ["Labor", "Fee", "Non-Travel Expenses", "Travel Expenses"]:
            if (alias, budget_category) not in existing_alias_budget_pairs:
                subtasks.append({
                    "line_item": 0,
                    "alias": alias,
                    "subtask_name": name,
                    "short_code": "N/A",
                    "budget_category": budget_category,
                    "category_amount": 0.0
                })

    # Grouped values
    cost_type_by_item = {}
    line_cost_by_item = defaultdict(list)

    for row in result:
        if row.item_no is None:
            continue  # skip project-level rows

        if row.word_tag == "cost_type" and row.word.strip().lower()!= "expenses":
            cost_type_by_item[row.item_no] = row.word.strip().lower()

        elif row.word_tag == "line_cost":
            try:
                cost = float(row.word.replace(",", "").replace("$", "").strip())
                line_cost_by_item[row.item_no].append(cost)
            except:
                continue

    # Initialize totals
    total_labor_amount = 0.0
    total_expenses_amount = 0.0
    total_travel_amount = 0.0
    total_tier_fee = 0.0
    total_budget_amount = 0.0

    for item_no, costs in line_cost_by_item.items():
        cost_type = cost_type_by_item.get(item_no, "")
        item_total = sum(costs)
        total_budget_amount += item_total

        if cost_type == "labor":
            total_labor_amount += item_total
        elif cost_type == "non-travel":
            total_expenses_amount += item_total
        elif cost_type == "travel":
            total_travel_amount += item_total
        elif cost_type == "fee":
            total_tier_fee += item_total

    project_data = {
        "project_name": project_name,
        "wo_number": wo_number,
        "bmcd_number": bmcd_form_number,
        "wo_date": wo_date,
        "po_number": po_number,
        "tao_number": tao_number,
        "contract_number": contract_number,
        "total_labor_amount": total_labor_amount,
        "total_expenses_amount": total_expenses_amount,
        "total_travel_amount": total_travel_amount,
        "total_tier_fee": total_tier_fee,
        "total_budget_amount": total_budget_amount,
        "subtasks": subtasks
    }

    return project_data

def create_project_from_files(pdf_db: Session, main_db: Session, bmcd_form_number: str):

    try:

        project_data = get_aggregated_data_from_temp_db(pdf_db, bmcd_form_number)
        new_project = Project(
            wo_date=project_data["wo_date"],
            project_name=project_data["project_name"],
            wo_number=project_data["wo_number"],
            bmcd_number=project_data["bmcd_number"],
            po_number=project_data["po_number"],
            tao_number=project_data["tao_number"],
            contract_number=project_data["contract_number"],
            total_labor_amount=project_data["total_labor_amount"],
            total_expenses_amount=project_data["total_expenses_amount"],
            total_travel_amount=project_data["total_travel_amount"],
            total_tier_fee=project_data["total_tier_fee"],
            total_budget_amount=project_data["total_budget_amount"]
        )

        main_db.add(new_project)
        main_db.flush()

        # Add subtasks if present
        for sub in project_data["subtasks"]:
            main_db.add(Subtask(
                project_id=new_project.id,
                subtask_name=sub["subtask_name"],
                alias=sub["alias"],
                short_code=sub["short_code"],
                line_item=sub["line_item"],
                budget_category=sub["budget_category"],
                category_amount=sub["category_amount"]
            ))

        main_db.commit()
        main_db.refresh(new_project)
        return new_project

    except Exception as e:
        main_db.rollback()
        print(e)
        raise e
    finally:
        pdf_db.close()
        main_db.close()
