# SocratiQ — The Socratic Class

An AI-assisted virtual classroom where the AI **coaches instead of answering** and instructors see the *learning process*
(attempts, coaching, verification, evidence), not just a final file.

```
Browser (React)  ──JWT──▶  FastAPI backend  ──SQL (transactions)──▶  Postgres + pgvector (Supabase)
   │  Supabase Auth            │  ├─ authorisation (app/access.py)          ▲
   └───────────────────────────┘  ├─ file pipeline (validate → store → extract → chunk → embed → index)
                                  └─ AI adapter ──▶  ai/  (LangGraph Coach · RAG · Verification)   [unchanged]
```

| Path | What it is |
|---|---|
| `frontend/socratiq/` | React + Vite UI (all screens, wired to the API and Supabase Auth) |
| `backend/app/` | FastAPI API: auth, authorisation, courses/assignments/attempts, file pipeline, analytics, AI adapter |
| `ai/` | The AI system (Coach graph, RAG, verification). **Not modified by the integration** (see `docs/INTEGRATION_AUDIT.md`) |
| `database/` | Migrations 000–013, migration runner, DB tests |
| `docs/` | Architecture, API, database, file pipeline, security, setup, testing, audit report |

## Quick start (development)

```bash
cp .env.example .env                       # fill DATABASE_URL, SUPABASE_*, AI_* (see docs/SETUP.md)
pip install -r requirements-dev.txt
python database/run_migrations.py          # new project. Existing project: see docs/SETUP.md §3
uvicorn backend.app.main:app --reload      # API on :8000 (docs at /docs in development)

cd frontend/socratiq && cp .env.example .env && npm ci && npm run dev    # UI on :5173
```

Or everything in containers: `docker compose up --build` (Auth/Storage still come from a Supabase project).

## What you can do

* **Instructors** create courses (each gets a random invite code), upload course materials in **any of 42 formats** (PDF, Word, PowerPoint,
  Excel/CSV, text/Markdown, images via OCR, source code, notebooks…), create assignments manually or from a file, publish/archive them,
  attach datasets/starter files, and review per-student learning evidence.
* **Students** join with an invite code, work on assignments, get Socratic coaching grounded in the course materials, submit files, and complete a
  short Explain → Modify → Transfer verification.
* The UI only offers file types the backend can genuinely process: it reads `GET /api/v1/files/capabilities` (see `docs/FILE_PIPELINE.md`).

## Tests

Real-Postgres suites: **AI 272 · database 43 · backend 116 · compatibility 12**, plus frontend type-check/build. See `docs/TESTING.md` for commands and what each suite proves.

## Read next

`docs/ARCHITECTURE.md` · `docs/FILE_PIPELINE.md` · `docs/SECURITY.md` · `docs/DATABASE.md` · `docs/API.md` · `docs/SETUP.md` · `docs/INTEGRATION_AUDIT.md`
