from app.main import app
from app.models import SessionLocal
from app.models.analysis import AnalysisResult, AnalysisStatus

# Test the endpoint directly
from fastapi.testclient import TestClient

client = TestClient(app)

# Test completed endpoint
response = client.get("/api/v1/analysis/completed")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Check database directly
db = SessionLocal()
completed = db.query(AnalysisResult).filter(
    AnalysisResult.status == AnalysisStatus.COMPLETED
).limit(5).all()

print(f"\nDirect DB query found {len(completed)} completed analyses")
for analysis in completed:
    print(f"  - {analysis.id}: {analysis.status}")

db.close()