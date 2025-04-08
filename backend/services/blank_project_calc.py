from collections import defaultdict
from typing import List
from decimal import Decimal, ROUND_HALF_UP

def calculate_totals(budget_categories: List[str], category_amounts: List[Decimal]) -> dict:
    totals = defaultdict(lambda: Decimal("0.00"))

    for category, amount in zip(budget_categories, category_amounts):
        key = category.strip().lower()
        if key == "labor":
            totals["labor"] += amount
        elif key == "fee":
            totals["fee"] += amount
        elif key in ("non-travel expenses", "non travel expenses"):
            totals["expenses"] += amount
        elif key == "travel expenses":
            totals["travel"] += amount

        totals["budget"] += amount  # all categories contribute to the total budget

    return {
        "labor": totals["labor"],
        "fee": totals["fee"],
        "expenses": totals["expenses"],
        "travel": totals["travel"],
        "budget": totals["budget"]
    }
