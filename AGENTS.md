# AGENTS.md — Flowsaic

Shared rules for every AI coding tool on this team and every teammate. Cursor reads this file automatically, and Claude Code reads it through `CLAUDE.md`. ChatGPT doesn't read files on its own, so paste this file into a ChatGPT Project's instructions or at the start of a chat. **If this file and your AI disagree, this file wins.**

The source of truth for scope, data and API shapes is the team's **Flowsaic Semester 1 Contract** doc (Nov 11, 2026). It replaces the old "Data & API Contracts" doc. If this file and the contract disagree, the contract wins. Fix this file.

## Goal right now

A working prototype, demoed live on a laptop on **Dec 7, 2026**. It doesn't have to be perfect. Polish happens in semester 2. If a task isn't on the demo path below, don't build it.

**Demo flow:** a student logs in with a sample account → sees their dashboard (degree progress, saved schedules) → either builds a schedule from the catalog with live conflict checking, or asks the AI to suggest one → saves it → sees it on a weekly calendar.

| In for Dec 7 | Out until semester 2 |
| --- | --- |
| Sample login (seeded demo students) | Real accounts, sign-up, password hashing |
| Dashboard: degree progress, saved schedules | Advisor side, messaging, confirm/deny |
| Catalog browse and search for one term | Multiple schools, branding, `institution_id` |
| Manual schedule builder with conflict check | Jenzabar integration |
| AI-suggested schedule (Gemini), checked by the same checker | FERPA hardening, audit logs, roles |
| RAG over course descriptions (pgvector) | Hosting, deployment |
| Weekly calendar view | Admin upload page for the export |
| Several saved schedules per student | Automated degree plan import |
| Degree map checkoff for completed courses | Complex degree rules |
| Any number of degree plans (format supports it) | |

Still a stretch goal: unofficial transcript upload.

## Project

Flowsaic is a web app for course scheduling and advising. Students get the course catalog, their degree map and a conflict-checking calendar in one place (a "mosaic" of the 3 tabs they juggle today). Launching at Southern Arkansas University (SAU) first. Flowsaic is a web application with a REST API backend. It is not itself an API.

## Owners and stack

One repo, one folder per part. Every piece talks to the next through the contract's endpoints only.

| Part | Tech | Folder | Owner | AI tool |
| --- | --- | --- | --- | --- |
| Front end | React | `/frontend` | Andy | Cursor / ChatGPT |
| Backend + AI (Gemini, RAG) | Python, FastAPI, Pydantic, SQLAlchemy, pytest | `/backend` | Victor | Claude Code |
| Database | Postgres (pgvector image), Alembic migrations | `/db` | Aaron, with Victor | Cursor / ChatGPT |
| Data files | SAU Excel export, degree plan JSON, course info CSV | `/data` | Aaron | Cursor / ChatGPT |

Don't change another owner's folder without telling them.

Backend entry point: `backend/app/main.py`. Run with `uv sync`, then `uv run fastapi dev app/main.py` from `backend/`. Live API docs at `/docs`.

## Run locally

1. `docker compose up -d` from the repo root starts Postgres 17 (pgvector image) on host port **5433** (5432 is often taken by a local Postgres). Copy the `DATABASE_URL` line from `backend/.env.example` into `backend/.env`.
2. From `backend/`: `uv sync`, then `uv run alembic upgrade head` builds the tables. Alembic lives in `backend/alembic/` because it imports the app's settings and models.
3. Run the seed scripts in order (see Data loading). Run them from `backend/` so they use its environment, e.g. `uv run python ..\db\scripts\load_course_info.py`.
4. `uv run python ..\db\scripts\check_db.py` confirms the connection and the pgvector extension.

Same database on every laptop.

## Rules for any AI assistant

- **Plan before code.** First give a short plan and list the files you'll touch. Wait for the developer's OK.
- **One task at a time.** Do only what was asked. Don't refactor unrelated code or touch another teammate's folder unless told to.
- **Stay in scope.** If the task drifts into a "semester 2" item, stop and say so.
- **No new dependencies** without asking and saying why.
- **Tests are part of the task.** Write tests, run them, show the results. A task with failing tests is not done.
- **Never run `git push`, delete files, or drop/reset database tables** without asking first.
- **Don't change the contract** without being told to. If the task seems to need it, stop and say so.
- **Say when you're unsure.** If a requirement is ambiguous or conflicts with this file, stop and ask instead of guessing.
- When finished: summarize what changed and anything to double-check.

## Ground rules (semester 1)

1. **Schema changes go through migrations only.** Nobody edits tables by hand. Aaron writes migrations; Victor asks him or opens a PR.
2. **Secrets** live in `.env` only, never committed: `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`. `.env.example` lists the names with placeholder values. Alembic reads the DB URL from settings, never from `alembic.ini`. **Never paste `.env` contents or real keys into any AI chat.** If a key is ever committed, tell the team and rotate it immediately; deleting the commit isn't enough.
3. **IDs are UUIDs** for our records. SAU codes (`CSCI 3103`, term codes) are plain text fields.
4. **Real student data stays out of the repo.** Demo students are fake. Real advising worksheets are format references only and are never committed or sent to the LLM.
5. **The LLM never decides validity.** Gemini picks sections and writes explanations. The schedule checker (code) decides whether a schedule is valid. The AI never saves anything.
6. **Errors** are always `{ "error": "snake_case_code" }` with the matching HTTP status. Never return stack traces or raw exceptions.
7. **SQL:** SQLAlchemy parameterized queries only. **No f-string or string-concatenated SQL.**
8. **Input:** validate with Pydantic models.
9. **CORS:** allow only the React dev server origin, never `*`.

## Formats

- Times: 24-hour `HH:MM`. Timestamps: ISO 8601 UTC.
- Days: letters from `MTWRFSU` (R = Thursday).
- JSON fields: `snake_case` everywhere, front end included. Missing values are `null`, not omitted.

## Data model

Eleven tables (plus the RAG table below). Each section's meeting time lives on the section row, because one export row is one section with one time. Labs (`002L`) are their own sections.

| Table | Fields | Notes |
| --- | --- | --- |
| `terms` | id, code, name | e.g. Spring 2027 |
| `courses` | id, code, title, department, credits, description, other_requirements | `code` like `CSCI 3103`; description from SAU catalog. `department` and `credits` come from the sections export, so they are `null` for courses not offered this term |
| `course_prereqs` | course_code, requires_code, option_group | One row per prereq. Rows sharing an `option_group` are alternatives (any one counts). Empty = no prereqs |
| `sections` | id, course_id, term_id, section_number, instructor, location, building, room, days, start_time, end_time, division, enrolled, capacity | Blank days/times = online or TBA. Blank instructor = "Staff". `start_time`/`end_time` are Postgres `time` columns; the API formats them as `HH:MM`. One row per (course, term, section number) |
| `degree_plans` | id, name, catalog_year, total_hours | e.g. BS Computer Science, 2023. `catalog_year` is text |
| `requirement_groups` | id, degree_plan_id, parent_id, name, rule, hours_required, sort_order | Tree of requirements |
| `requirement_courses` | group_id, course_code | Courses that count toward a group |
| `students` | id, name, email, password, degree_plan_id, classification | Demo accounts only. Plain demo password is fine for semester 1 |
| `completed_courses` | student_id, course_code, status | `completed` or `in_progress` |
| `schedules` | id, student_id, term_id, name, source, created_at | source = `manual` or `ai` |
| `schedule_sections` | schedule_id, section_id | |

`course_code` columns are plain text, not foreign keys, so a degree plan can list courses not offered this term.

Computed on read, never stored: `seats_open = capacity - enrolled` (floor 0), and degree progress.

## Degree plan format

One JSON file per plan in `/data/degree_plans/`. Adding a plan = writing a file and re-running the seed script, no code changes. For Dec 7: BS Computer Science and Poultry Science, entered by hand.

A plan is a tree of requirement groups. Each group has one rule:
- `all`: every listed course and child group must be done.
- `choose_hours`: completed listed courses must add up to `hours_required`.

A parent group is met when its own rule is met and all its children are met. See the contract for a full JSON example. Not handled in semester 1: "only one Art and one Music course," residency hours, upper-level hour totals, transfer substitutions (shown as plain text notes only).

## Data loading

Scripts in `/db/scripts/`, run from `backend/` (`uv run python ..\db\scripts\<name>.py`). Re-running updates rows instead of duplicating them. Scripts 1 and 2 work in either order; 3–5 come after them. **Built so far (Nov 16): 1, 2 and 5, plus `search.py`.** 3 and 4 are not written yet.

1. `import_sections.py`: SAU export → terms, courses, sections. **Loaded Nov 16: 1,323 sections, 861 courses offered.**
   - Current file (Nov 16): `/data/sections_spring_2027.csv` (renamed from `flowsaic_sections course cataglogs.csv`), ~1,415 sections. Columns: `course_section, title, term, department, start_time, end_time, days, campus, building, room, instructor, level, credits, enrolled, capacity, concurrent`.
   - Normalize times (`09:00:AM` → `09:00`, `01:30:PM` → `13:30`) and days (`M W F` → `MWF`). Blank times/days = online or TBA. `level` = division (UG/GR). `credits` like `3.0` → integer.
   - Older exports were an HTML table with an `.xls` name; read those with `pd.read_html(path)[0]`.
   - Last token of the course code is the section (`001`, `002L`, `001H`); the rest is the course code. Insert a missing space (`SCM6003` → `SCM 6003`).
   - Skip the Concurrent column. Bad rows are printed and skipped, never guessed.
   - **One meeting time per section** (decided Nov 16). The export lists 86 sections on 2–3 rows, one per meeting time (lecture plus an evening exam slot, or an in-person row plus a "Hybrid Course" row). The importer loads the row with the most meeting days (ties: first in the file) and prints the other 87 rows as "extra meeting time, not loaded". The checker can't see those extra times; see Open questions.
   - Sections whose title starts with `CANCELED` (5 rows) are printed and skipped.
   - A course already in `courses` only gets `department` and `credits` filled in; the catalog title wins. A course missing from the catalog gets a minimal row (85 of them, all graduate level, no description).
   - Term `code` is SAU's export text as is (`2026-2027 - Spring`); `name` is `Spring 2027`.
   - 37 sections have days but no times (mostly high-school concurrent sections). They load with days and blank times.
2. `load_course_info.py`: `/data/course_info.csv`. **Done Nov 16: 1,878 courses** from SAU's public 2026–27 catalog (raw scrape + rebuild script in `/data/raw/`; re-run `python build_course_info.py` to regenerate without scraping again).
   - Columns: `code, title, description, prereqs, other_requirements, prereq_text, coreqs, coreq_text, needs_review`.
   - `prereqs`: `;` = all required, `|` = any one of these. Example: `CHEM 3103;MATH 1023|MATH 1053` = CHEM 3103 AND (MATH 1023 OR MATH 1053). Load each `|` group with a shared `option_group`. Every `;` group gets a number starting at 1, so a single required course is a group of one. **Loaded Nov 16: 1,025 prereq rows across 603 courses.** Re-running replaces a course's prereq rows, so a fixed CSV fixes the table.
   - **Known data problem:** 15 courses mix `;` and `|` in a way that encodes lecture/lab pairs wrongly (e.g. BIOL 2061: `CHEM 1013;CHEM 1011|CHEM 1023;CHEM 1021` loads as CHEM 1013 AND (CHEM 1011 OR CHEM 1023) AND CHEM 1021, but the catalog means one lecture+lab pair OR the other). The checker would block wrongly on these; 8 are offered this term. Fix in the CSV, not the loader.
   - `other_requirements` (instructor permission, standing, admission): stored, **not enforced** in semester 1.
   - `needs_review` (120 rows, also in `/data/course_info_needs_review.csv`): prereqs too complex to parse are left **blank** so the checker never blocks wrongly; 10 courses have no description because SAU's own pages are broken. Fix by hand only the ones on demo plans.
3. `load_degree_plans.py`: every JSON file in `/data/degree_plans/`.
4. `seed_demo.py`: 3 fake students on different plans and stages (freshman, junior, senior) with completed courses checked off.
5. `embed_course_info.py` (RAG, after 1–2): chunks and embeds course descriptions into `doc_chunks`. See RAG. **Done Nov 16: 1,868 chunks.** It skips courses whose chunk text is already stored, so a re-run resumes and costs nothing.
6. `search.py "query"`: test tool. Embeds the query and prints the top 8 courses (code, title, cosine distance).

## Schedule checker

One Python function checks every schedule, manual or AI. Input: a student and a list of section IDs. Output: `{ "conflicts": [...], "warnings": [...] }`. Conflicts block saving; warnings don't.

| Check | Result | Code |
| --- | --- | --- |
| Two sections meet on the same day at overlapping times | Conflict | `time_overlap` |
| A required prereq isn't completed or in progress (for an OR group: none of its options is) | Conflict | `missing_prereq` |
| Same course added twice | Conflict | `duplicate_course` |
| Course already completed | Warning | `already_completed` |
| Section is full | Warning | `section_full` |
| Course isn't on the student's degree plan | Warning | `not_on_plan` |
| Total credits over 18 | Warning | `over_credit_limit` |

Overlap: same day and `start_a < end_b and start_b < end_a`. Online/TBA sections never cause a time conflict. Lecture/lab pairing is not enforced in semester 1.

Each item: `{ "code": "time_overlap", "section_ids": ["...", "..."], "message": "CSCI 3103 and MATH 2753 overlap on MW 10:00" }`. The front end shows `message` as is.

## AI suggest (Gemini)

1. Student fills the preferences form and hits Suggest.
2. Backend gathers remaining requirements, completed/in-progress courses, and eligible sections for the term (on the plan, not completed, prereqs met). This keeps the prompt small.
3. Backend sends Gemini the preferences, requirements and eligible sections (plus RAG context, see below) and asks for JSON only: `{ "section_ids": [...], "explanation": "..." }`.
4. Backend runs the checker on the result.
5. On conflicts, send them back to Gemini and ask for a fix. Maximum 3 tries.
6. Return the schedule, explanation and warnings. If all 3 tries fail, return the best attempt with its conflicts shown.

Preferences are all optional: `term_id`, `target_credits`, `unavailable` (list of `{days, start, end}`), `preferred_time` (`morning` / `afternoon` / `evening` / blank), `lunch`, `preferred_instructors`, `avoid_instructors`, `notes`. Gemini treats preferences as wishes and checker rules as hard limits.

- Model name and key come from `.env` (`GEMINI_MODEL`, `GEMINI_API_KEY`), so switching models is a one-line change.
- **Set a spending cap in the Google account before the first call.**
- Send the LLM course data and preferences only. Never student names, emails or IDs; use the student's degree plan and course codes.
- Validate Gemini's JSON with Pydantic. Reject section IDs that weren't in the eligible list.

## RAG (part of the system)

RAG is a core part of Flowsaic, not a stretch goal (decided Nov 16; the contract's RAG section matches). It gives Gemini the course text SQL rows can't: descriptions and catalog/policy wording.

Decided:
- **One Postgres database with pgvector.** No separate vector DB.
- **RAG is for unstructured text only** (course descriptions, catalog/policy text). Structured data (sections, times, prereqs, degree plans, completed courses) always comes from SQL, never from vector search.
- RAG context is extra input to the AI suggest prompt. It never replaces the eligible-sections list or the checker.
- Embeddings are generated ahead of time by a script (`embed_course_info.py`, after `load_course_info.py`), not per request (except embedding the query). Re-running updates rows instead of duplicating.
- **Embedding model: Gemini Embedding 2 (`gemini-embedding-2`) at 768 dimensions** (decided Nov 16). Same Google account and key as Gemini Flash. Request 768 dims explicitly (the default is 3,072). The vector column is `vector(768)`. Name lives in `.env` as `EMBEDDING_MODEL`.
- Never mix vectors from different models. Changing the model means re-running `embed_course_info.py` for every row.

- **`doc_chunks` table** (built Nov 16): id, source_type, source_code, chunk_index, content, embedding `vector(768)`, created_at. Unique on (source_type, source_code, chunk_index). Course chunks use `source_type = 'course'`, `source_code` = the course code, `chunk_index = 0`.
- **How to call `gemini-embedding-2`** (from Google's docs, confirmed by a live call Nov 16). All of this lives in `backend/app/embeddings.py`; use its helpers, don't call the API directly.
  - Send each text as its own `Content` object. A plain list of strings is merged into **one** embedding.
  - The model has no `task_type` setting. The task goes in the text, and documents and queries must always use these formats: documents as `title: CSCI 3103 Data Structures | text: <description>`, queries as `task: search result | query: <query>`.
  - Vectors at 768 dimensions come back already normalized.
- **Rate limits:** the free tier allows 1,000 embeddings a day per model (each text counts as one, even in a batch; resets at midnight Pacific), so a full embed doesn't fit in one day. Billing was turned on Nov 16. Every search query also uses one request.

Retrieval settings (Nov 16):
- **Corpus:** course descriptions only, all 1,868 courses that have one (format: `code title: description`). Policy text can come later in ~300–500 token chunks (that's what `chunk_index` is for).
- **Chunks:** one per course. `doc_chunks.content` stores `CSCI 3103 Data Structures: <description>`; the text sent to Gemini is the same chunk in the document format above, so the embedding knows what it's about.
- **Filter first:** required courses search only the student's eligible codes; electives and catalog search cover every course offered that term.
- **Query:** the student's `notes` plus preferences as a sentence. Empty `notes` = skip RAG for that request.
- **Ranking:** cosine distance, HNSW index (`vector_cosine_ops`), top 8.
- **Embed script** sends descriptions in batches to stay under rate limits. Embedding all of them costs a few cents.

## API endpoints

Sixteen endpoints. Everything except login needs the session cookie and acts on the logged-in student.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{ email, password }` | Student; sets session cookie |
| POST | `/auth/logout` | | 204 |
| GET | `/me` | | Student name, plan, classification |
| GET | `/me/progress` | | Requirement tree, each group met/not met, hours done/needed |
| GET | `/me/completed-courses` | | List of `{ course_code, status }` |
| PUT | `/me/completed-courses` | `{ courses: [{ course_code, status }] }` | Replaces the whole list |
| GET | `/terms` | | Terms for the dropdown |
| GET | `/courses` | Query: `term_id` (required), `search`, `department`, `on_my_plan` | Courses with their sections |
| GET | `/courses/{id}` | | Course, description, prereqs, sections |
| POST | `/schedules/check` | `{ term_id, section_ids }` | `{ conflicts, warnings }` |
| GET | `/schedules` | | My saved schedules |
| POST | `/schedules` | `{ name, term_id, section_ids, source }` | Saved schedule, or 422 with conflicts |
| GET | `/schedules/{id}` | | Schedule with full section details for the calendar |
| PUT / DELETE | `/schedules/{id}` | Same body as POST / none | Updated schedule / 204 |
| POST | `/ai/suggest` | Preferences | `{ section_ids, sections, explanation, warnings, conflicts }` |

The dashboard uses `/me`, `/me/progress` and `/schedules`; there's no separate dashboard endpoint. Exact response fields are defined in the backend's `/docs` (FastAPI generates them). Andy reads `/docs`, not this table, for field names. Front end builds against mock JSON in that shape until the endpoint is live.

## Definition of done

An endpoint is done when it matches the contract, has tests, and passes `pytest`. For the checker and AI suggest: tests cover every conflict/warning code, and AI suggest is tested with Gemini mocked (no real API calls in tests).

## Git

- Repo is **private** (`huaandy/Flowsaic`).
- Everyone works on their own branch (`backend/...`, `frontend/...`, `db/...`). Nothing merges into `main` without a pull request reviewed by one other teammate.
- Check `git status` before every commit. Never commit `.env`, database dumps, real student data, or keys.
- Ask before pushing.
- **Changing the contract:** say it in the group chat, update the contract doc, update this file, then change code.

## Current status

(Each owner updates their line every work session.)
- Team: Aaron Ezell, Andy Hua, Victor Santamaria. Supervisor: Dr. Ahmad Al-Shami.
- Contract: Semester 1 Contract is current, including the RAG section added Nov 16.
- Backend (Nov 16): rebuilt from scratch on `backend/foundation`, not committed yet. Working: app skeleton with `GET /health`, settings from `.env`, all models, one Alembic migration, the loaders for sections and course info, embeddings, and `search.py`. 46 tests pass. Not built yet: every other endpoint, CORS, the schedule checker, AI suggest, `load_degree_plans.py`, `seed_demo.py`. Next: catalog endpoints, schedule checker, Gemini + RAG.
- Course data: `/data/course_info.csv` done (1,878 courses, Nov 16). Not committed yet.
- Database (Victor, Nov 16): Postgres 17 + pgvector 0.8.7 in Docker on port 5433. Migration `0001` creates the eleven tables plus `doc_chunks` with an HNSW cosine index. Loaded: 1 term, 1,963 courses, 1,025 prereq rows, 1,323 sections, 1,868 embedded chunks. Empty: degree plans, students, schedules.
- Front end: _fill in_

## Decisions log

- **Nov 16:** the earlier database/RAG scripts (`documents`/`chunks` tables, keyword search, `ingest.py`, `api.py`, `load_courses.py`) are **replaced** by the contract schema. Don't use or copy them. Victor builds the new schema and migrations.
- **Nov 16:** schema built. Additions beyond the contract's field lists, which the contract doc still needs: `courses.other_requirements` (nullable text), `sections.start_time`/`end_time` as `time` columns, `degree_plans.catalog_year` as text, and the `doc_chunks` shape in the RAG section.
- **Nov 16:** sections importer keeps one meeting time per section and skips canceled sections (see Data loading).
- **Nov 16:** embedding text formats for `gemini-embedding-2` are fixed (see RAG). Changing them means re-embedding every row.
- **Nov 16:** local database runs on host port 5433, bound to this laptop only (`127.0.0.1` and `::1`). Its dev-only password is in `docker-compose.yml`; it protects fake data in a local container and must never be reused.

## Open questions (don't build around these yet)

- **Sections with more than one meeting time.** 86 sections have 2–3 meeting times, but `sections` stores one, so the conflict checker misses 87 real meeting times. Storing them needs a meetings table, which is a contract change.
- **Mixed AND/OR prereqs.** 15 courses are encoded wrongly in `course_info.csv` (see Data loading). Decide whether to fix them by hand or blank them like the other `needs_review` rows.
- **High-school concurrent sections** (39 rows, `concurrent = Yes`) are loaded like any other section. Decide whether the catalog should hide them.

## Semester 2 (parked, don't build before Dec 7)

Kept here so these aren't lost. They come back when the real product starts:
- **Multi-tenancy:** `institution_id` on every table, taken from the session only; cross-institution access returns 404.
- **Real auth:** server-side sessions in HttpOnly/Secure/SameSite cookies; argon2/bcrypt hashing; login rate limits; roles `student` / `advisor` / `admin`, default-deny.
- **Advisor side:** queue, confirm/deny matching SAU's Jenzabar approval, messaging. Status flow `draft → submitted → approved | denied`.
- **FERPA hardening:** audit log on every read/change of a student record; no personal data in logs; strip identifying info before any LLM call; check the LLM provider's no-training/retention terms; encryption at rest; HTTPS only; `/docs` off in production.
- **Jenzabar roadmap:** no access → read-only API → write access. Never use student credentials or scrape behind a login.
- **Other:** multiple schools and branding, complex degree rules, deployment, WCAG 2.1 AA accessibility.
