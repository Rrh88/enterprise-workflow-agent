"""Data contracts. Every later phase (extraction, agent, API) uses these."""
from datetime import date
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    amount: float


class Invoice(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: date
    due_date: date | None = None
    currency: str = "INR"
    line_items: list[LineItem]
    subtotal: float
    tax_rate: float  # percent, e.g. 18
    tax_amount: float
    total: float


class ExtractionResult(BaseModel):
    """What the extractor returns: the invoice plus per-field confidence (0-1)."""
    invoice: Invoice
    confidence: dict[str, float] = {}


class Issue(BaseModel):
    code: str
    field: str
    message: str


class Decision(BaseModel):
    route: str  # AUTO_APPROVE | HUMAN_REVIEW | REJECT
    reasons: list[str] = []
    issues: list[Issue] = []
