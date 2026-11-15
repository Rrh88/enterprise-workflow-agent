import json
from pathlib import Path

import pytest

from app import workflow
from app.schemas import Invoice
from app.workflow import build_graph, process, resume

GOLD = {json.loads(p.read_text())["file"]: json.loads(p.read_text())
        for p in sorted(Path("data/golden").glob("*.json"))}


@pytest.fixture
def graph(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(workflow, "AUDIT", tmp_path / "audit.jsonl")

    def fake_extract(doc_path):  # stands in for Gemini: returns the golden label for that document
        return Invoice(**GOLD[Path(doc_path).name]["invoice"]), {"input_tokens": 1, "output_tokens": 1}

    return build_graph(fake_extract)


def pick(defect):
    return next(f for f, r in GOLD.items() if r["defect"] == defect)


def test_clean_invoice_is_auto_posted(graph):
    cfg, out = process(graph, "data/invoices/" + pick(None))
    assert out["status"] == "posted" and "__interrupt__" not in out


def test_defective_invoice_pauses_then_human_approves(graph):
    cfg, out = process(graph, "data/invoices/" + pick("wrong_total"))
    assert "__interrupt__" in out                      # paused, waiting for a human
    final = resume(graph, cfg, "approve", by="rohit")
    assert final["status"] == "posted"


def test_human_can_reject(graph):
    cfg, out = process(graph, "data/invoices/" + pick("wrong_tax"))
    final = resume(graph, cfg, "reject")
    assert final["status"] == "rejected_by_human"


def test_duplicate_is_rejected_once_original_is_posted(graph):
    dup_file = pick("duplicate")
    src = GOLD[dup_file]["invoice"]
    orig = next(f for f, r in GOLD.items() if r["invoice"] == src and f != dup_file)
    cfg, out = process(graph, "data/invoices/" + orig)
    if "__interrupt__" in out:  # the original may itself carry a defect, so a human posts it
        out = resume(graph, cfg, "approve")
    assert out["status"] == "posted"
    cfg2, out2 = process(graph, "data/invoices/" + dup_file)
    assert out2["status"] == "rejected"