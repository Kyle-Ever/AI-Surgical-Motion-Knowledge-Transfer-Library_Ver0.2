# Repository Guidelines

## Project Structure & Module Organization
- FastAPI entrypoint `backend/app/main.py` registers routers in `backend/app/api/routes/` for videos, analysis (v1/v2), scoring, library, and instrument tracking.
- Primary orchestration lives in `backend/app/services/`; `analysis_service_v2.py` pairs detector factories in `app/services/detectors/` with metrics and websocket updates.
- Models and session wiring sit in `backend/app/models/`, pydantic schemas in `backend/app/schemas/`, shared config/error handling in `backend/app/core/`, and ML primitives in `backend/ai_engine/processors/`.
- Uploads land in `backend/data/uploads/`, temp frames in `backend/data/temp/`, while the Next.js frontend (`frontend/`) and docs (`docs/`) round out the repo.

## Build, Test, and Development Commands
- `start_backend_py311.bat` sets up `venv311`, installs `backend/requirements.txt`, and runs `uvicorn app.main:app --reload --port 8000`.
- `start_frontend.bat` or `cd frontend && npm install && npm run dev` serves the UI at http://localhost:3000; `start_both.bat` boots both tiers.
- Use `python -m pytest backend/tests` or targeted scripts (for example `python backend/test_comparison_api.py`) during backend work, then run `python test_integration.py` once the API is live.

## Coding Style & Naming Conventions
- Follow PEP 8, four-space indentation, and full type hints; share helpers through `backend/app/core/`, keep modules snake_case, and models PascalCase.
- Services stay thin orchestrators (see `analysis_service_v2.py`), and frontend code uses two-space indentation, PascalCase components, camelCase hooks (`useScoreStream`), and must pass `npm run lint`.

## Testing Guidelines
- Pytest drives coverage; keep probes beside features as `backend/test_<feature>.py`, noting they expect SQLite `aimotion.db` and bundled media under `backend/data/`.
- Toggle `.env` flags like `SAM_DEVICE=cpu` for SAM cases (for example `backend/test_sam_tracking.py`); Playwright runs via `cd frontend && npm ci && npx playwright install --with-deps && npm run test` with the API running.

## Commit & Pull Request Guidelines
- Commits use imperative prefixes (`feat:`, `fix:`, `Frontend:`) and PRs must explain the change, link issues, and list executed tests with results.
- Attach UI evidence when visuals shift, add rollback notes, and split unrelated backend experiments into separate branches.

## Security & Configuration Tips
- Store secrets in `backend/.env`; never commit credentials, `.db` snapshots, or raw uploads.
- `backend/app/core/config.py` pins `numpy<2`; watch disk usage by clearing `backend/data/temp/` during large uploads.

## Agent-Specific Workflow
- Log plan, touched files, tests, and risks in `tasks.md`, and update `docs/PRD/PRD-001_aimotion.md` when backend behavior changes.
- Prefer `analysis_v2` endpoints (`backend/app/api/routes/analysis_v2.py`) and document any reliance on legacy `analysis_service.py`.
