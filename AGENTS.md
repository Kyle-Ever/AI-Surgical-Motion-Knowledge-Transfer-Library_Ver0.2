# Repository Guidelines

## Project Structure & Module Organization
The FastAPI backend lives in `backend/`; entrypoint `app/main.py`, routers under `app/api/routes/`, shared helpers in `app/core/`, and models split between `app/models/` and Pydantic schemas in `app/schemas/`. ML workflows stay in `ai_engine/processors/`. The Next.js frontend sits in `frontend/` with routes in `app/`, shared React code in `components/` and `hooks/`, utilities in `lib/`, and static assets in `public/`. Long-lived assets belong in `data/` (`data/uploads/` for uploads, `data/temp/` for scratch), while process docs are in `docs/`.

## Build, Test, and Development Commands
Run `start_backend.bat` to provision Python 3.11, install `backend/requirements.txt`, and launch FastAPI at `http://localhost:8000`. Use `start_frontend.bat` or `cd frontend && npm install && npm run dev` to serve the UI on port 3000; `start_both.bat` brings up both tiers. With the backend active, execute `python test_integration.py` for API coverage. For UI regression, run `cd frontend && npm ci && npx playwright install --with-deps && npm run test`.

## Coding Style & Naming Conventions
Python modules use snake_case filenames, four-space indentation, full type hints, and PascalCase classes; keep shared logic in `app/core/`. JavaScript/TypeScript files use two-space indentation, React components in PascalCase, hooks camelCase (`useExample`), and Tailwind utility classes for styling. Respect formatter and lint configs; run `npm run lint` in `frontend/` before committing UI code.

## Testing Guidelines
Backend unit or ad-hoc tests live beside their modules as `backend/test_*.py`. Start the API before running Playwright suites (`npm run test`) or `python test_integration.py`. Favor selectors tied to stable UI copy to avoid flaky frontend tests, and add focused coverage whenever behavior changes.

## Commit & Pull Request Guidelines
Write commit messages in imperative prefixes such as `feat: add kinematics processor` or `Frontend: update layout`. Pull requests should describe the change, link issues, attach UI screenshots or recordings when visuals shift, list executed test commands with results, and note rollback considerations.

## Security & Configuration Tips
Do not commit secrets or `.env` files. Keep dependencies within the `numpy<2` boundary to preserve OpenCV and MediaPipe support. Target `http://localhost:8000` for API calls, where CORS is preconfigured, and keep SQLite data local-only.

## Agent-Specific Workflow
For multi-step contributions, update `docs/PRD/PRD-001_aimotion.md` and `tasks.md`, record Plan/Files/Test/Risk before coding, implement the minimal diff, and validate acceptance criteria before handoff.
