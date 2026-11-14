"""Show exactly where the extractor was wrong on the hard set, and which defects the validator missed."""
import json
import sys
from pathlib import Path

from app.schemas import Invoice
from app.validation import validate

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.5-flash-lite"
cache = json.loads(Path(f"results/{MODEL}_hard.json").read_text())
levels = json.loads(Path("data/hard/levels.json").read_text())
EXPECTED = {"wrong_total": "TOTAL_MISMATCH", "wrong_tax": "TAX_MISMATCH",
            "bad_dates": "DATE_ORDER", "duplicate": "DUPLICATE"}
FIELDS = ["invoice_number", "vendor_name", "invoice_date", "due_date", "currency",
          "subtotal", "tax_rate", "tax_amount", "total"]


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 0.01
    return str(a).strip().lower() == str(b).strip().lower()


seen = set()
for g in sorted(Path("data/golden").glob("*.json")):
    rec = json.loads(g.read_text())
    gold, got, defect = rec["invoice"], cache[g.stem]["invoice"], rec["defect"]
    codes = {i.code for i in validate(Invoice(**got), seen)}

    diffs = [f"{f}: expected {gold[f]} got {got[f]}" for f in FIELDS if not same(gold[f], got[f])]
    gl, el = gold["line_items"], got["line_items"]
    if len(gl) != len(el):
        diffs.append(f"line_items: expected {len(gl)} rows, got {len(el)} rows")
    else:
        for i, (a, b) in enumerate(zip(gl, el)):
            for k in ("description", "quantity", "unit_price", "amount"):
                if not same(a[k], b[k]):
                    diffs.append(f"line {i + 1} {k}: expected {a[k]} got {b[k]}")

    missed = defect in EXPECTED and EXPECTED[defect] not in codes
    if diffs or missed:
        print(f"\n{g.stem} [{levels[g.stem]}] defect={defect}")
        for d in diffs:
            print("   WRONG:", d)
        if missed:
            print(f"   VALIDATOR MISSED {defect} (expected {EXPECTED[defect]}, found {sorted(codes)})")