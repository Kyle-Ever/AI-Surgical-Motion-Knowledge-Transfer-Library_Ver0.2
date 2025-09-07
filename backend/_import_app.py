import sys
from pathlib import Path

# Ensure backend root on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import app.main as m
    print("IMPORT_OK", bool(getattr(m, "app", None)))
except Exception as e:
    print("IMPORT_ERROR", type(e).__name__, str(e))

