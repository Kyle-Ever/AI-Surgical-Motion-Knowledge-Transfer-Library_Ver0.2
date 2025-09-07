import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
import app.main as m

client = TestClient(m.app)
r = client.get(f"{m.settings.API_V1_STR}/health" if hasattr(m, 'settings') else "/api/v1/health")
print("status=", r.status_code)
print("json=", r.json())

