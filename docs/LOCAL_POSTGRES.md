# Running the integrated PostgreSQL version

The local branch `codex/postgres-topic-completion` integrates upstream
`feat/topic-completion-tracking` at `4f2a906` with the PostgreSQL migration and
authenticated session work. The original work is preserved at local commit
`eafc64e`. No remote branch was changed.

## Open the app

- App: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Dependency health: http://localhost:8000/health
- PostgreSQL: 127.0.0.1:5433, database `ai_tutor_db`.
- Generated local account credentials: `LOCAL_ACCESS.md` in the repository root.

Sign in as the student to try manual completion. Select a concept, open its tutor,
and click **Mark as Done**. The skill tree displays **Completed** for that student.
Completion is separate from assessment-based mastery; it does not invent a quiz
score or change mastery percentages.

The included Database Foundations course contains original demo notes. Upload
your own PDF, TXT, or Markdown as an instructor or administrator. Without a
`GROQ_API_KEY`, answers use relevant extracted passages and slide match metadata.
The deterministic Hill cipher solver does not require a model key or textbook
retrieval.

## Restart on this Windows machine

From the repository root, using PowerShell 7:

```powershell
./scripts/start.ps1
```

This starts the isolated PostgreSQL cluster, FastAPI, and the compiled Next.js
application in the background. The installed PostgreSQL 18 binaries are used;
the existing system database services are independent of this cluster.

Stop this application's processes and isolated database with:

```powershell
./scripts/stop.ps1
```

Database files remain in `.runtime/postgres`; vector data remains in
`chroma_data`. Do not delete either directory to restart the app. Logs are in
`.runtime/logs`. Secrets and runtime data are gitignored.

## Apply future changes

Stop the app before rebuilding the production frontend. Start PostgreSQL before
running migrations or integration tests. The bootstrap script reads the local
owner credential from `.runtime/postgres-owner-password`, applies only unapplied
numbered migrations, and grants the application role access to new objects.
It does not reset existing accounts or drop course data.

```powershell
python -m pip install -r backend/requirements.txt
python scripts/bootstrap_postgres.py
npm ci --prefix frontend
npm run build --prefix frontend
python -m pytest -q
./scripts/start.ps1
```

The active schema is `database/postgres/*.sql`. MySQL SQL files, the SQLite
fallback module, original root-level backend test scripts, and earlier viva
documentation remain as upstream history; they are not the active runtime or
test suite. `pytest.ini` selects `backend/tests`.

## Verification on 2026-11-04

- 22 integration tests passed against a fresh, isolated PostgreSQL test database.
- Production frontend build and TypeScript checks passed.
- Browser: signed in, asked a question, received retrieved course passages,
  marked a topic complete, and observed its Completed badge in the skill tree.
- The integration suite verifies completion idempotency, persistence across
  sign-ins, student isolation, valid roles/topics, and chat logging for numerical
  answers, alongside the existing session, mastery, rollback, and vector tests.

This deployment listens only on the local machine. It has not been published to
public hosting. PostgreSQL data and Chroma persistence must be backed up together;
the vector write journal supports recovery for this single-host setup.
