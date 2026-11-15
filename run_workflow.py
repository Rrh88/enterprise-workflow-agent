"""Run the whole workflow on one document with the real Gemini extractor.
Usage: python run_workflow.py [document] [model]"""
import sys

from app.extractor import Extractor
from app.workflow import build_graph, process, resume

doc = sys.argv[1] if len(sys.argv) > 1 else "data/invoices/inv_010.pdf"
model = sys.argv[2] if len(sys.argv) > 2 else "gemini-3.5-flash-lite"

graph = build_graph(Extractor(model).extract)
cfg, out = process(graph, doc)

if "__interrupt__" in out:
    req = out["__interrupt__"][0].value
    inv = req["invoice"]
    print("\n=== PAUSED: HUMAN REVIEW NEEDED ===")
    print("Invoice:", inv["invoice_number"], "|", inv["vendor_name"], "| total", inv["total"])
    print("Reasons:", req["reasons"])
    print("Issues :", [i["code"] for i in req["issues"]])
    answer = input("Approve and post? (y/n): ").strip().lower()
    out = resume(graph, cfg, "approve" if answer == "y" else "reject", by="rohit")

print("\nFINAL STATUS:", out["status"])