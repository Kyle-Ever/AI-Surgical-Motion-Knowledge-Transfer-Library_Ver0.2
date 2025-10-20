"""Database shim for backward-compatibility.

This module re-exports the canonical SQLAlchemy objects from `app.models` to
maintain compatibility for imports that still reference `app.models.database`.
Prefer importing from `app.models` and concrete model modules directly.
"""

from . import engine, SessionLocal, Base, get_db  # noqa: F401
from .analysis import AnalysisResult, AnalysisStatus  # noqa: F401

