"""Library endpoints for completed analyses.

NOTE: get_completed_analyses and export_analysis were removed to eliminate
duplication with analysis.py, which provides superior implementations
(joinedload for N+1 prevention, include_failed/include_details options,
richer CSV export with skeleton frame data).

Use the analysis router equivalents instead:
  - GET  /api/v1/analysis/completed          (was /api/v1/library/completed)
  - GET  /api/v1/analysis/{id}/export        (was /api/v1/library/export/{id})
"""
from fastapi import APIRouter

router = APIRouter()
