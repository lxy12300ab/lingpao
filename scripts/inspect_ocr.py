"""Run from project root: python -m scripts.inspect_ocr image.png 2026-09-19."""
import json
import sys
from datetime import date
from app.ocr import recognize

print(json.dumps(recognize(sys.argv[1], date.fromisoformat(sys.argv[2])), ensure_ascii=False, indent=2))
