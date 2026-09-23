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








