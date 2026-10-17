# healthapp — MVP building blocks

```
backend/   FastAPI + asyncpg + Anthropic SDK
flutter/   lib/ (models, api, services, screens) + test/ + pubspec.yaml + PLATFORM_SETUP.md
```

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Database: must be UTF8 with a UTF-8 locale (Supabase default is fine). With SQL_ASCII or the plain
# "C" locale pg_trgm silently produces no trigrams for Japanese; the app refuses to start in that case.
psql "$DATABASE_URL" -f sql/001_schema.sql

export DATABASE_URL=postgresql://...      # asyncpg DSN
export ANTHROPIC_API_KEY=...              # server only, never in the app
uvicorn app.main:app --reload
```

| Env | Default | Meaning |
|---|---|---|
| `MODEL_TEXT` | `claude-haiku-5-5` | text-only meals |
| `MODEL_VISION` | `claude-sonnet-5-5` | any request with a photo |
| `EFFORT_TEXT` / `EFFORT_VISION` | `low` / `medium` | reasoning depth per route |
| `MASTER_SIM_THRESHOLD` | `0.8` | trigram similarity to accept a master row |

Tests: `pytest` (unit tests + fake LLM). With `TEST_DATABASE_URL=postgresql://...` (a throw-away DB, its
`public` schema is wiped) the master-lookup and API tests run against real Postgres too.

Auth is a stub (`X-User-Id` header in `app/main.py: current_user_id`). Replace it before exposing the API.

Seed the shared master (`foods`, `user_id = null`) with `name_norm = normalize_food_name(name)` and
`chain_norm = normalize_chain_name(chain)` computed by the same Python functions used at query time.

## Flutter

Copy `lib/` and `test/` into your app, merge `pubspec.yaml` dependencies, follow `PLATFORM_SETUP.md`.
`flutter analyze && flutter test` — see `lib/example/wiring.dart` for how the pieces connect.
