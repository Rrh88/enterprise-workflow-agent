"""LangGraph workflow: extract -> validate/decide -> (act | human review | reject).
State is checkpointed per document (thread_id), so a paused review survives and resumes."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .schemas import ExtractionResult, Invoice
from .validation import decide

LEDGER = Path("data/ledger.jsonl")  # stand-in for the accounting system (one line per posted invoice)
AUDIT = Path("data/audit.jsonl")    # every step is recorded here


class State(TypedDict, total=False):
    doc_path: str
    invoice: dict
    confidence: dict
    usage: dict
    route: str
    reasons: list
    issues: list
    review: dict
    status: str


def key_of(inv: dict) -> str:
    return f"{inv['vendor_name'].strip().lower()}|{inv['invoice_number'].strip().lower()}"


def ledger_keys() -> set:
    if not LEDGER.exists():
        return set()
    return {json.loads(l)["key"] for l in LEDGER.read_text().splitlines() if l.strip()}


def audit(doc: str, step: str, **info):
    AUDIT.parent.mkdir(exist_ok=True)
    rec = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "doc": doc, "step": step, **info}
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def build_graph(extract_fn: Callable, checkpointer=None):
    """extract_fn(doc_path) -> (Invoice, usage_dict[, confidence_dict]). Injected so tests need no API."""

    def extract(state: State):
        out = extract_fn(state["doc_path"])
        inv, usage = out[0], out[1]
        conf = out[2] if len(out) > 2 else {}
        audit(state["doc_path"], "extract", tokens=usage)
        return {"invoice": inv.model_dump(mode="json"), "usage": usage, "confidence": conf}

    def validate_decide(state: State):
        # duplicates are judged against what is already posted in the ledger
        seen = {tuple(k.split("|")) for k in ledger_keys()}
        res = ExtractionResult(invoice=Invoice(**state["invoice"]), confidence=state.get("confidence", {}))
        d = decide(res, seen)
        audit(state["doc_path"], "decide", route=d.route, reasons=d.reasons, issues=[i.code for i in d.issues])
        return {"route": d.route, "reasons": d.reasons, "issues": [i.model_dump() for i in d.issues]}

    def route_after_decide(state: State) -> str:
        return {"AUTO_APPROVE": "act", "HUMAN_REVIEW": "human_review"}.get(state["route"], "reject")

    def human_review(state: State):
        # Nothing with side effects may come before interrupt(): on resume this node restarts from the top.
        answer = interrupt({"doc": state["doc_path"], "invoice": state["invoice"],
                            "reasons": state["reasons"], "issues": state["issues"]})
        audit(state["doc_path"], "human_review", decision=answer.get("decision"), by=answer.get("by", "unknown"))
        if answer.get("decision") == "approve":
            edits = answer.get("edits") or {}
            return {"review": answer, "invoice": {**state["invoice"], **edits}}
        return {"review": answer, "status": "rejected_by_human"}

    def route_after_review(state: State) -> str:
        return "reject" if state.get("status") == "rejected_by_human" else "act"

    def act(state: State):
        k = key_of(state["invoice"])
        if k in ledger_keys():  # idempotency: a replay or retry must not post the same invoice twice
            audit(state["doc_path"], "act", result="already_posted", key=k)
            return {"status": "already_posted"}
        LEDGER.parent.mkdir(exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps({"key": k, "total": state["invoice"]["total"],
                                "posted_at": time.time(), "doc": state["doc_path"]}) + "\n")
        audit(state["doc_path"], "act", result="posted", key=k)
        return {"status": "posted"}

    def reject(state: State):
        status = state.get("status") or "rejected"
        audit(state["doc_path"], "reject", reasons=state.get("reasons"))
        return {"status": status}

    g = StateGraph(State)
    g.add_node("extract", extract)
    g.add_node("validate_decide", validate_decide)
    g.add_node("human_review", human_review)
    g.add_node("act", act)
    g.add_node("reject", reject)
    g.add_edge(START, "extract")
    g.add_edge("extract", "validate_decide")
    g.add_conditional_edges("validate_decide", route_after_decide, ["act", "human_review", "reject"])
    g.add_conditional_edges("human_review", route_after_review, ["act", "reject"])
    g.add_edge("act", END)
    g.add_edge("reject", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def process(graph, doc_path: str):
    """Run one document. Returns the final state, or the pending review request if paused."""
    cfg = {"configurable": {"thread_id": Path(doc_path).stem}}
    result = graph.invoke({"doc_path": doc_path}, cfg)
    return cfg, result


def resume(graph, cfg, decision: str, by: str = "reviewer", edits: dict | None = None):
    return graph.invoke(Command(resume={"decision": decision, "by": by, "edits": edits or {}}), cfg)