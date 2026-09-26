# Task API

A CRUD API for managing tasks, built as part of the FlyRank Backend AI Engineering internship. Originally an in-memory API (Assignment 1), then SQLite-backed (Assignment 2), now running on PostgreSQL in Docker (Containerization stage, current).

## Run it (current — Postgres + Docker)

1. Clone this repo and enter the folder:

git clone https://github.com/nailaanjum/flyrank-backend-ai-engineering.git 
cd flyrank-backend-ai-engineering

2. Copy the example environment file:

copy .env.example .env

3. Start everything — API and database together:

docker compose up

4. Open `http://localhost:8000/docs` to try the API interactively, or hit `http://localhost:8000/tasks` directly.

HTTP/1.1 200 OK
date: Mon, 07 Sep 2026 19:45:02 GMT
server: uvicorn
content-length: 105
content-type: application/json

[[1,"Learn FastAPI",false],[2,"Learn PostgreSQL",false],[3,"Build CRUD API",false],[4,"learn llm",false]]


## Environment variables

Copy `.env.example` to `.env` before running standalone (outside Compose). It defines:

DATABASE_URL=postgres://username:password@localhost:5432/dbname

When run via `docker compose up`, the real connection string is set in `compose.yaml`, pointing at the `db` service rather than `localhost`.

## Endpoints

| Method | Path          | What it does                          |
|--------|---------------|-----------------------------------------|
| GET    | `/`           | Basic info about the API                |
| GET    | `/health`     | Confirms the API is running             |
| GET    | `/tasks`      | Lists every task                        |
| GET    | `/tasks/{id}` | Gets one task by its id (404 if missing)|
| POST   | `/tasks`      | Creates a task (400 if title empty/missing, 201 on success) |
| PUT    | `/tasks/{id}` | Updates a task's title/done status (404 if missing) |
| DELETE | `/tasks/{id}` | Deletes a task (204 on success, 404 if missing) |

## Example request

curl -i http://localhost:8000/tasks

HTTP/1.1 200 OK
date: Mon, 07 Sep 2026 19:45:02 GMT
server: uvicorn
content-length: 105
content-type: application/json

[[1,"Learn FastAPI",false],[2,"Learn PostgreSQL",false],[3,"Build CRUD API",false],[4,"learn llm",false]]
## Database

Confirmed directly inside the running Postgres container:

docker exec -it crud_api-db-1 psql -U postgres -d tasks -c "\dt"
docker exec -it crud_api-db-1 psql -U postgres -d tasks -c "SELECT * FROM tasks;"

![Database contents](database-proof.png)

## Tech stack

Python, FastAPI, PostgreSQL, psycopg, Docker, Docker Compose

## Local dev — running the database standalone (without Compose)

docker run --name taskdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=tasks -p 5432:5432 -v taskdata:/var/lib/postgresql -d postgres
















# Task API

A small CRUD API for managing tasks, built as part of the FlyRank Backend AI Engineering internship (Week 3, Assignments 1–2).

## Assignment 1 — In-memory CRUD API

- `GET /tasks` — list all tasks
- `GET /tasks/{id}` — get a single task by id (404 if not found)
- `POST /tasks` — create a task (400 if `title` is missing/empty, 201 on success)
- `PUT /tasks/{id}` — update a task (404 if not found, 400 if body is invalid)
- `DELETE /tasks/{id}` — delete a task (204 on success, 404 if not found)

> Note: this stage stored tasks in memory only — data reset every time the server restarted. This limitation was removed in Assignment 2 (see below).

**Screenshot (Swagger UI):**

![Swagger UI](swagger-ui.png)


## Assignment 2 — SQLite persistence

Starting from this stage, all endpoints above read from and write to a real database instead of an in-memory list. The API surface (routes, status codes, validation rules) is unchanged — only where the data lives has changed.

**Why SQLite:** single file, zero setup, no separate server process to install or run, and it survives restarts — which makes it a good fit for a small project like this.

**Where the database lives:** `tasks.db`, created automatically the first time the app runs. It's git-ignored, so every fresh clone starts with a clean database and reseeds the three example tasks.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT 0
);
```

### Running the project

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
<< REPLACE WITH YOUR ACTUAL START COMMAND, e.g. uvicorn main:app --reload >>
```

On first run, `tasks.db` is created automatically, the `tasks` table is set up, and three example tasks are seeded. On every run after that, the seed step is skipped because the table is no longer empty.

### Exploring the database directly

Opened `tasks.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and ran queries by hand in the "Execute SQL" tab. Example:

```sql
SELECT * FROM tasks WHERE done = 1;
```

**Result:** << REPLACE — e.g. "returned the 2 tasks that had been marked complete via PUT" >>

Changes made in DB Browser show up immediately through `GET /tasks`, with no server restart needed — the API and DB Browser are reading the exact same file, so there's one source of truth, not two things kept "in sync."

**Screenshot:** `docs/Database.png`
![DB Browser](Database.png)

### Checkpoints verified

- [x] Restarting the app three times still shows exactly 3 seeded tasks (not 6, not 9)
- [x] `GET /tasks` and `GET /tasks/{id}` read live from `tasks.db`
- [x] `POST /tasks` persists across a server restart
- [x] `PUT`/`DELETE` update the database; correct status codes (200, 204, 404) confirmed
- [x] Hand-run SQL queries in DB Browser are reflected instantly through the API
- [x] Clean clone + one command → working app with table and 3 seeded tasks, no manual setup

## Tech stack

Python, FastAPI, SQLite (`sqlite3`)


## Local dev — database

Start Postgres:
docker run --name taskdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=tasks -p 5432:5432 -v taskdata:/var/lib/postgresql -d postgres


## LLM API

This project integrates an LLM using the OpenAI-compatible SDK.

The LLM provider and model are configurable through environment
variables (`LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`),
allowing compatible providers to be switched without changing
application code.


## Stage 2 — Prompt v1 and real LLM

The `/triage` endpoint was connected to the local Gemma model through Ollama.

The system prompt is stored separately in:

`prompts/triage-v1.md`

The prompt is loaded at runtime and sent as the `system` message. The customer's support message is sent separately as the `user` message and is JSON-encoded before being sent to the model.

Temperature was set to `0` to reduce unnecessary variation in classification results.

### Test inputs

1. Billing:
   `I was charged twice for my subscription.`

2. Bug:
   `The dashboard crashes every time I try to open it.`

3. Ambiguous:
   `Something is wrong with my account.`

### Observations

The model generally followed the requested JSON structure and used the categories defined in the prompt. The exact wording of the `reason` field and the confidence value can vary between model responses.

The ambiguous input was useful for checking whether the model followed the instruction to use `other` with low confidence instead of guessing.

The prompt is kept separate from user content so that untrusted input is not inserted into the system instructions. This also provides a basic defense against prompt injection.

### Stage 2 result

The endpoint successfully returned real responses from Gemma with `LLM_STUB=0`.

The versioned prompt is stored in `prompts/triage-v1.md`.


## Retry policy

We disable the SDK's own default retries and implement our own: up to 2 retries,
only on timeouts, 429, and 5xx responses, using exponential backoff (1s, 2s, 4s)
plus jitter, and honoring `Retry-After` when the provider sends one. 400, 401,
and 403 are never retried — they are permanent failures for that specific request,
and retrying them would only waste quota.

### Note on testing the no-retry-on-401 behavior

Our provider for this project is local Ollama (`http://localhost:11434`), which
does not enforce API key validation — it accepts any value for `LLM_API_KEY`,
including an intentionally invalid one, and still processes the request
successfully. This means we could not observe a real `401` end-to-end against
our own running provider.

The retry logic itself explicitly excludes `400`, `401`, and `403` from the
retry loop (see `call_model` in `src/routes/triage.py`) and only retries on
`APITimeoutError`, `RateLimitError`, and 5xx `APIStatusError`s. This exclusion
was verified by code inspection rather than a live 401 from our provider.
With another day, we'd temporarily point the client at a hosted provider like
OpenRouter (which does enforce real keys) to observe a genuine 401 and confirm
the no-retry path end-to-end.


## Eval results
Date: 2026-09-26
Prompt version: triage-v1
Result: 8/8 matched (100%)

Note: this is a small, hand-picked eval set (8 cases) meant to catch obvious
regressions when the prompt changes — a 100% pass rate here reflects strong
performance on these specific cases, not a guarantee of correctness on the
full range of real-world inputs. See evals/cases.json and evals/run_eval.py
to reproduce.

## Cost log (sample)
{"prompt_version": "triage-v1", "model": "gemma3:1b", "input_tokens": 493, "output_tokens": 50, "duration_ms": 19898.83, "needed_repair": false}

Our provider (local Ollama) is free, so this specific setup costs $0 regardless
of volume. For reference, if run against a small hosted model priced around
$0.15/1M input tokens and $0.60/1M output tokens: at 10,000 requests/day
(4.93M input tokens + 500K output tokens), the estimated cost would be
roughly $1.04/day (~$31/month).

## What I'd fix with another day
Our local provider (Ollama) doesn't enforce API key validation, so we
couldn't observe a real 401 to confirm the "never retry on 401" behavior
end-to-end — only by code inspection. With another day, I'd temporarily
test against a hosted provider like OpenRouter to verify that path for real.


