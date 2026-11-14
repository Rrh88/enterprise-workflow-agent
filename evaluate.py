"""Run extraction on a golden set and print an accuracy report.
Usage: python evaluate.py [model] [pdf|hard]
  pdf  = the clean PDFs in data/invoices (default)
  hard = the degraded images in data/hard
Results are cached in results/, so a stopped run resumes where it left off."""
import json
import sys
from pathlib import Path

from app.extractor import Extractor
from app.schemas import Invoice
from app.validation import validate

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.5-flash-lite"
SET = sys.argv[2] if len(sys.argv) > 2 else "pdf"
HARD = SET == "hard"
DOC_DIR = Path("data/hard") if HARD else Path("data/invoices")
EXT = "jpg" if HARD else "pdf"
OUT = Path("results")
OUT.mkdir(exist_ok=True)
CACHE = OUT / (f"{MODEL}_hard.json" if HARD else f"{MODEL}.json")
LEVELS = json.loads(Path("data/hard/levels.json").read_text()) if HARD else {}

FIELDS = ["invoice_number", "vendor_name", "invoice_date", "due_date",
          "currency", "subtotal", "tax_rate", "tax_amount", "total"]
EXPECTED = {"wrong_total": "TOTAL_MISMATCH", "wrong_tax": "TAX_MISMATCH",
            "bad_dates": "DATE_ORDER", "duplicate": "DUPLICATE"}


def close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 0.01
    return str(a).strip().lower() == str(b).strip().lower()


def items_ok(got, gold):
    return len(got) == len(gold) and all(
        close(g["description"], w["description"]) and close(g["quantity"], w["quantity"])
        and close(g["unit_price"], w["unit_price"]) and close(g["amount"], w["amount"])
        for g, w in zip(got, gold))


cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
golds = sorted(Path("data/golden").glob("*.json"))

# ---- Step 1: extract (skips documents already done) ----
ex = Extractor(MODEL)
in_a_row = 0
for g in golds:
    if g.stem in cache and "error" not in cache[g.stem]:
        continue
    try:
        inv, usage = ex.extract(DOC_DIR / f"{g.stem}.{EXT}")
        cache[g.stem] = {"invoice": inv.model_dump(mode="json"), "usage": usage}
        in_a_row = 0
        print(g.stem, "done")
    except Exception as e:
        cache[g.stem] = {"error": str(e)[:300]}
        in_a_row += 1
        print(g.stem, "FAILED:", str(e)[:120])
    CACHE.write_text(json.dumps(cache, indent=2))
    if in_a_row >= 3:
        print("3 failures in a row (probably a daily limit). Stopping; run again later to resume.")
        break

# ---- Step 2: score ----
field_ok = {f: 0 for f in FIELDS}
n = items = full = fails = tin = tout = 0
caught = defects = false_alarms = clean = inj_ok = inj_n = 0
by_level = {}
wrong_fields = {}
seen = set()
for g in golds:
    rec = json.loads(g.read_text())
    gold, defect = rec["invoice"], rec["defect"]
    r = cache.get(g.stem)
    if not r or "invoice" not in r:
        fails += 1
        continue
    got = r["invoice"]
    n += 1
    tin += r["usage"]["input_tokens"] or 0
    tout += r["usage"]["output_tokens"] or 0
    good = {f: close(got[f], gold[f]) for f in FIELDS}
    for f in FIELDS:
        field_ok[f] += good[f]
        if not good[f]:
            wrong_fields.setdefault(g.stem, []).append(f)
    li = items_ok(got["line_items"], gold["line_items"])
    if not li:
        wrong_fields.setdefault(g.stem, []).append("line_items")
    items += li
    doc_ok = all(good.values()) and li
    full += doc_ok
    if HARD:
        lv = LEVELS.get(g.stem, "?")
        c = by_level.setdefault(lv, [0, 0])
        c[0] += 1
        c[1] += doc_ok
    codes = {i.code for i in validate(Invoice(**got), seen)}
    if defect in EXPECTED:
        defects += 1
        caught += EXPECTED[defect] in codes
    elif defect is None:
        clean += 1
        false_alarms += bool(codes)
    if defect == "injection":
        inj_n += 1
        inj_ok += doc_ok

print(f"\n=== {MODEL} on {SET}: {n} extracted, {fails} failed or pending (of {len(golds)}) ===")
if n:
    for f in FIELDS:
        print(f"{f:16s} {field_ok[f] / n:6.1%}")
    print(f"{'line_items':16s} {items / n:6.1%}")
    print(f"{'FULL INVOICE':16s} {full / n:6.1%}")
    if HARD:
        for lv in ("mild", "medium", "severe"):
            if lv in by_level:
                t, ok = by_level[lv]
                print(f"  full-invoice accuracy at {lv:7s}: {ok}/{t} = {ok / t:.0%}")
    print(f"validator caught {caught}/{defects} defective invoices; false alarms on {false_alarms}/{clean} clean ones")
    print(f"injection documents extracted correctly: {inj_ok}/{inj_n}")
    print(f"avg tokens per invoice: {tin // n} in, {tout // n} out")
    if wrong_fields:
        print("\nWrong fields (first 15 invoices):")
        for k in list(wrong_fields)[:15]:
            print(" ", k, LEVELS.get(k, ""), wrong_fields[k])