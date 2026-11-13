import json
from pathlib import Path
from app.schemas import Invoice, ExtractionResult
from app.validation import validate, decide

GOLD = sorted((Path(__file__).parent.parent / "data" / "golden").glob("*.json"))
EXPECTED = {"wrong_total": "TOTAL_MISMATCH", "wrong_tax": "TAX_MISMATCH",
            "bad_dates": "DATE_ORDER", "duplicate": "DUPLICATE"}


def test_golden_set_exists():
    assert len(GOLD) >= 50


def test_validator_catches_injected_defects_and_passes_clean():
    seen = set()
    for f in GOLD:  # processed in order, like a real stream (duplicates come later)
        rec = json.loads(f.read_text())
        codes = {i.code for i in validate(Invoice(**rec["invoice"]), seen)}
        if rec["defect"] in EXPECTED:
            assert EXPECTED[rec["defect"]] in codes, f.name
        else:
            assert not codes, (f.name, codes)  # clean + injection docs have consistent numbers


def test_routing():
    inv = Invoice(**json.loads(GOLD[0].read_text())["invoice"])
    assert decide(ExtractionResult(invoice=inv, confidence={"total": 0.99})).route == "AUTO_APPROVE"
    assert decide(ExtractionResult(invoice=inv, confidence={"total": 0.60})).route == "HUMAN_REVIEW"
    key = (inv.vendor_name.lower(), inv.invoice_number.lower())
    assert decide(ExtractionResult(invoice=inv), seen={key}).route == "REJECT"
