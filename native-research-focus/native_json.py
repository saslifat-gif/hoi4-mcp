"""Read durable JSON receipts; Windows publication handles open-file collisions."""
import json
from pathlib import Path

def read_receipt(path):
 return json.loads(Path(path).read_text(encoding="utf-8"))
