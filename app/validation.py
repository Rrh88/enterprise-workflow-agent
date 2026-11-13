"""Rule engine + routing. Deterministic checks run AFTER the LLM, never trusting it blindly."""
from datetime import date
from .schemas import Invoice, Issue, ExtractionResult, Decision

TOL = 0.011  # rounding tolerance in currency units
CONF_THRESHOLD = 0.85      # per-field; tune from eval data, do not treat as fixed
HIGH_AMOUNT = 1_000_000.0  # above this a human must approve


def validate(inv: Invoice, seen: set[tuple[str, str]] | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for i, li in enumerate(inv.line_items):
        if abs(li.quantity * li.unit_price - li.amount) > TOL:
            issues.append(Issue(code="LINE_MISMATCH", field=f"line_items[{i}]",
                                message="quantity x unit_price != amount"))
    if abs(sum(li.amount for li in inv.line_items) - inv.subtotal) > TOL:
        issues.append(Issue(code="SUBTOTAL_MISMATCH", field="subtotal",
                            message="sum of line items != subtotal"))
    if abs(inv.subtotal * inv.tax_rate / 100 - inv.tax_amount) > TOL:
        issues.append(Issue(code="TAX_MISMATCH", field="tax_amount",
                            message="subtotal x tax_rate != tax_amount"))
    if abs(inv.subtotal + inv.tax_amount - inv.total) > TOL:
        issues.append(Issue(code="TOTAL_MISMATCH", field="total",
                            message="subtotal + tax != total"))
    if inv.due_date and inv.due_date < inv.invoice_date:
        issues.append(Issue(code="DATE_ORDER", field="due_date",
                            message="due_date is before invoice_date"))
    if inv.invoice_date > date.today():
        issues.append(Issue(code="FUTURE_DATE", field="invoice_date",
                            message="invoice_date is in the future"))
    if seen is not None:
        key = (inv.vendor_name.strip().lower(), inv.invoice_number.strip().lower())
        if key in seen:
            issues.append(Issue(code="DUPLICATE", field="invoice_number",
                                message="same vendor + invoice number already processed"))
        seen.add(key)
    return issues


def decide(res: ExtractionResult, seen: set[tuple[str, str]] | None = None) -> Decision:
    issues = validate(res.invoice, seen)
    reasons: list[str] = []
    if any(i.code == "DUPLICATE" for i in issues):
        return Decision(route="REJECT", reasons=["duplicate invoice"], issues=issues)
    if issues:
        reasons.append("validation issues")
    low = [f for f, c in res.confidence.items() if c < CONF_THRESHOLD]
    if low:
        reasons.append(f"low confidence: {', '.join(sorted(low))}")
    if res.invoice.total > HIGH_AMOUNT:
        reasons.append("high amount")
    return Decision(route="HUMAN_REVIEW" if reasons else "AUTO_APPROVE",
                    reasons=reasons, issues=issues)
