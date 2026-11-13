# Enterprise Workflow Agent (Invoice Processing, Human-in-the-Loop)

Reads invoices (PDF/image), extracts structured data with a pre-trained vision LLM, validates it with
deterministic rules, and routes each document: auto-approve, human review, or reject.

## Status
- [x] Phase 1: use case (invoices) + labelled synthetic dataset (60 PDFs, 22 with injected defects)
- [x] Phase 3 (foundation): schemas, rule engine, confidence/amount routing, tests
- [ ] Phase 2: extraction (OCR + vision LLM, JSON schema output) + baseline accuracy
- [ ] Phase 4: LangGraph workflow (extract -> validate -> decide -> action), retries, checkpointing
- [ ] Phase 5: human-in-the-loop approval (interrupt/resume), review queue
- [ ] Phase 6: guardrails (prompt injection set already in data: defect = "injection")
- [ ] Phase 7: evaluation (field accuracy, escalation rate, cost/doc, failure analysis)
- [ ] Phase 8: FastAPI, UI, Docker, tracing, demo, docs/architecture.md

## Run
    pip install -r requirements.txt
    python data/generate_synthetic.py 60
    pytest

## Dataset labels (data/golden/*.json)
`invoice` = what the PDF shows; `defect` = wrong_total | wrong_tax | bad_dates | duplicate | injection | null.
