import sys
import json

from app.extractor import Extractor
from app.validation import validate

name = sys.argv[1] if len(sys.argv) > 1 else "inv_001"

ex = Extractor("gemini-3.5-flash-lite")
inv, usage = ex.extract(f"data/invoices/{name}.pdf")

gold = json.load(open(f"data/golden/{name}.json"))["invoice"]
got = inv.model_dump(mode="json")

print(json.dumps(got, indent=2))
print("tokens:", usage)
print("matches golden exactly:", got == gold)
print("validation issues:", [i.code for i in validate(inv)])