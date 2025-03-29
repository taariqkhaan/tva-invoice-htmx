from sqlalchemy.orm import Session
from backend.models import ExtractedWord


def assign_po_tags(db_session: Session):
    # Fetch all rows from the database where source_table is "po_table"
    rows = db_session.query(ExtractedWord).filter_by(source_table="po_table").order_by(ExtractedWord.page_no).all()

    # Convert to a list of dictionaries for easier access
    data = [{"id": row.id, "Word": row.word} for row in rows]

    # Helper functions
    def get_word(index):
        if 0 <= index < len(data):
            return data[index]["Word"]
        return None

    def get_id(index):
        if 0 <= index < len(data):
            return data[index]["id"]
        return None

    po_num_found = False
    po_desc_found = False
    appr_date_found = False
    cont_num_found = False
    app_amount_found = False

    i = 0
    item_no = None
    while i < len(data):
        word = get_word(i)
        next_word = get_word(i + 1)
        next_next_word = get_word(i + 2)

        # PO Number
        if word == "PO" and next_word == "Num:" and not po_num_found:
            if next_next_word:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 2)).update({"word_tag": "po_num"})
                po_num_found = True
                i += 2

        # PO Description
        elif word == "PO" and next_word == "Desc:" and not po_desc_found:
            j = i + 2
            while j < len(data) and get_word(j) != "Approved":
                db_session.query(ExtractedWord).filter_by(id=get_id(j)).update({"word_tag": "po_desc"})
                j += 1
            i = j - 1
            po_desc_found = True

        # PO Approved Date
        elif word == "Approved" and next_word == "Date:" and not appr_date_found:
            if next_next_word:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 2)).update({"word_tag": "po_appr_date"})
                appr_date_found = True
                i += 2

        # Contract Number
        elif word == "Contract:" and not cont_num_found:
            if next_word:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 1)).update({"word_tag": "contract_num"})
                cont_num_found = True
                i += 1

        # PO Approval Amount
        elif word == "Approval" and next_word == "Amount:" and not app_amount_found:
            if next_next_word:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 2)).update({"word_tag": "appr_amount"})
                app_amount_found = True
                i += 2

        # LINE ITEM TAGGING LOGIC

        # Step 1: Line Num
        elif word == "Line" and next_word == "Num:":
            item_no = get_word(i + 2)
            if item_no:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 2)).update({
                    "word_tag": "line_no",
                    "item_no": item_no
                })
            i += 2

        # Step 2: Alias → Cost Types
        elif word.strip("()") in ("M2", "B9", "N1", "T1", "H1", "G1", "N4", "F1", "HC") and item_no:
            db_session.query(ExtractedWord).filter_by(id=get_id(i)).update({
                "word_tag": "alias",
                "item_no": item_no
            })

            j = i + 1
            while j < len(data) and get_word(j) != "Item":
                db_session.query(ExtractedWord).filter_by(id=get_id(j)).update({
                    "word_tag": "cost_type",
                    "item_no": item_no
                })
                j += 1
            i = j - 1

        # Step 3: Line Cost
        elif word == "Line" and next_word == "Cost:" and item_no:
            if next_next_word:
                db_session.query(ExtractedWord).filter_by(id=get_id(i + 2)).update({
                    "word_tag": "line_cost",
                    "item_no": item_no
                })
            item_no = None
            i += 2

        i += 1

    # Cleanup: delete rows where word_tag is null or empty, only for source_table == "po_table"
    db_session.query(ExtractedWord).filter(
        ExtractedWord.source_table == "po_table",
        (ExtractedWord.word_tag == None) | (ExtractedWord.word_tag == "")
    ).delete(synchronize_session=False)

    db_session.commit()

def assign_tao_tags(db_session: Session):
    # Fetch and sort all relevant rows from the database
    rows = db_session.query(ExtractedWord)\
        .filter(ExtractedWord.source_table == "tao_table")\
        .order_by(ExtractedWord.page_no)\
        .all()

    # Convert to a list of dictionaries for easier access
    data = [{"id": row.id, "Word": row.word} for row in rows]

    # Helper functions
    def get_word(index):
        if 0 <= index < len(data):
            return data[index]["Word"]
        return None

    def get_id(index):
        if 0 <= index < len(data):
            return data[index]["id"]
        return None

    # Tag flags
    po_num_found = False
    tao_num_found = False
    tao_desc_found = False
    proj_num_found = False
    wo_num_found = False
    total_bug_found = False

    i = 0
    while i < len(data):
        word = get_word(i)
        next_word = get_word(i + 1)
        next_next_word = get_word(i + 2)

        # PO Number
        if word == "PO" and not po_num_found:
            target_id = get_id(i + 1)
            if target_id:
                db_session.query(ExtractedWord).filter_by(id=target_id).update({"word_tag": "po_num"})
                po_num_found = True

        # TAO Number
        elif word == "Date:" and not tao_num_found:
            target_id = get_id(i + 2)
            if target_id:
                db_session.query(ExtractedWord).filter_by(id=target_id).update({"word_tag": "tao_num"})
                tao_num_found = True

        # TAO Description
        elif word == "Description:" and not tao_desc_found:
            j = i + 1
            while j < len(data):
                if get_word(j) == "Project":
                    tao_desc_found = True
                    break
                target_id = get_id(j)
                if target_id:
                    db_session.query(ExtractedWord).filter_by(id=target_id).update({"word_tag": "tao_desc"})
                j += 1
            i = j - 1

        # Project Number
        elif word == "Project" and next_word == "Number:" and not proj_num_found:
            target_id = get_id(i + 2)
            if target_id:
                db_session.query(ExtractedWord).filter_by(id=target_id).update({"word_tag": "proj_num"})
                proj_num_found = True

        # WO Number
        elif word == "Order" and next_word == "No:" and not wo_num_found:
            target_id = get_id(i + 2)
            if target_id:
                db_session.query(ExtractedWord).filter_by(id=target_id).update({"word_tag": "wo_num"})
                wo_num_found = True

        # Alias short
        elif word in ["M2", "B9", "N1", "T1", "H1", "G1", "N4", "F1", "HC"]:
            alias_id = get_id(i)
            code_id = get_id(i + 1)
            if alias_id:
                db_session.query(ExtractedWord).filter_by(id=alias_id).update({"word_tag": "short_alias"})
            if code_id:
                db_session.query(ExtractedWord).filter_by(id=code_id).update({"word_tag": "short_code"})

        # # Alias with budget
        # elif word in ["(M2)", "(B9)", "(N1)", "(T1)", "(H1)", "(G1)", "(N4)", "(F1)", "(HC)"]:
        #     alias_id = get_id(i)
        #     total_id = get_id(i + 1)
        #     if alias_id:
        #         db_session.query(ExtractedWord).filter_by(id=alias_id).update({"word_tag": "alias"})
        #     if total_id:
        #         db_session.query(ExtractedWord).filter_by(id=total_id).update({"word_tag": "alias_budget"})

        # Total Budget
        elif word == "Total:" and not total_bug_found:
            total_id = get_id(i + 1)
            if total_id:
                db_session.query(ExtractedWord).filter_by(id=total_id).update({"word_tag": "total_budget"})
                total_bug_found = True

        i += 1

    # Cleanup: delete rows with empty or null word_tag for tao_table
    db_session.query(ExtractedWord).filter(
        ExtractedWord.source_table == "tao_table",
        (ExtractedWord.word_tag == None) | (ExtractedWord.word_tag == "")
    ).delete(synchronize_session=False)

    db_session.commit()

def check_docs(db_session: Session):

    sync_tags(db_session)
    results = (
        db_session.query(ExtractedWord.word, ExtractedWord.source_table)
        .filter(
            ExtractedWord.word_tag == "po_num",
            ExtractedWord.source_table.in_(["po_table", "tao_table"])
        )
        .all()
    )

    word_dict = {row.source_table: row.word for row in results}
    po_word = word_dict.get("po_table")
    tao_word = word_dict.get("tao_table")

    if po_word and tao_word and po_word == tao_word:
        return {
            "validation_status": "success",
            "validation_message": "Purchase Order Number Validated!"
        }
    else:
        return {
            "validation_status": "error",
            "validation_message": "Purchase Order Number Validation Failed!   Check PO and TAO!"
        }

def sync_tags(db_session: Session):
    # ----------- WO_NUM -----------
    tao_wo_words = (
        db_session.query(ExtractedWord.word)
        .filter(
            ExtractedWord.word_tag == "wo_num",
            ExtractedWord.source_table == "tao_table"
        )
        .all()
    )

    wo_words = [row.word for row in tao_wo_words]

    # Find matching words in po_table
    po_wo_matches = (
        db_session.query(ExtractedWord)
        .filter(
            ExtractedWord.word.in_(wo_words),
            ExtractedWord.source_table == "po_table"
        )
        .all()
    )

    for word_entry in po_wo_matches:
        word_entry.word_tag = "wo_num"

    # ----------- TAO_NUM -----------
    tao_tao_words = (
        db_session.query(ExtractedWord.word)
        .filter(
            ExtractedWord.word_tag == "tao_num",
            ExtractedWord.source_table == "tao_table"
        )
        .all()
    )

    tao_words = [row.word for row in tao_tao_words]

    po_tao_matches = (
        db_session.query(ExtractedWord)
        .filter(
            ExtractedWord.word.in_(tao_words),
            ExtractedWord.source_table == "po_table"
        )
        .all()
    )

    for word_entry in po_tao_matches:
        word_entry.word_tag = "tao_num"

    db_session.commit()
