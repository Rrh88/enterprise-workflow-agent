"""Human review queue.
  python review.py list              -> show documents waiting for a human
  python review.py <document> y|n    -> approve (y) or reject (n) a waiting document"""
import sys

from app.workflow import build_graph, resume, sqlite_checkpointer


def no_extract(path):
    raise RuntimeError("extraction must not run again when resuming a review")


saver = sqlite_checkpointer()
graph = build_graph(no_extract, saver)


def waiting():
    threads = sorted({c.config["configurable"]["thread_id"] for c in saver.list(None)})
    pending = []
    for t in threads:
        state = graph.get_state({"configurable": {"thread_id": t}})
        if state.next == ("human_review",):
            pending.append((t, state.values))
    return pending


if len(sys.argv) < 2 or sys.argv[1] == "list":
    queue = waiting()
    if not queue:
        print("Nothing waiting for review.")
    for t, v in queue:
        inv = v["invoice"]
        print(f"{t}: {inv['invoice_number']} | {inv['vendor_name']} | total {inv['total']} | reasons {v['reasons']}")
elif len(sys.argv) >= 3 and sys.argv[2].lower() in ("y", "n"):
    cfg = {"configurable": {"thread_id": sys.argv[1]}}
    out = resume(graph, cfg, "approve" if sys.argv[2].lower() == "y" else "reject", by="rohit")
    print("FINAL STATUS:", out["status"])
else:
    print("Usage: python review.py list   |   python review.py <document> y|n")