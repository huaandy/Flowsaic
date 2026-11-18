# AGENTS.md — Flowsaic

Shared rules for every AI coding tool on this team and every teammate. Cursor reads this file automatically, and Claude Code reads it through `CLAUDE.md`. ChatGPT doesn't read files on its own, so paste this file into a ChatGPT Project's instructions or at the start of a chat. **If this file and your AI disagree, this file wins.**

The source of truth for scope, data and API shapes is the team's **Flowsaic Semester 1 Contract** doc, **version 2 (Nov 17, 2026)**. It replaces version 1 (Nov 11) and the old "Data & API Contracts" doc. If this file and the contract disagree, the contract wins. Fix this file.

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
| Several saved schedules per student | Course Search fallback when the schedule export fails |
| Degree map checkoff for completed courses | Complex degree rules |
| | Hosting the mySAU connect browser anywhere but the demo laptop |
| Any number of degree plans (format supports it) | |
| Automated data retrieval: public scrapers + student-run mySAU connect (Nov 17) | |

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

Backend entry point: `backend/app/main.py`. Run with `uv sync`, then `uv run fastapi dev app/main.py` from `backend/`. Open http://127.0.0.1:8000/ for the prototype sign-in page (then the tabbed test page at `/dev`). Live API docs at `/docs`. Don't edit backend `.py` files while a mySAU connect is running: `fastapi dev` reloads on changes and the reload kills the connect.

## Run locally

**The easy way (Windows):** install [Git](https://git-scm.com/) and [Docker Desktop](https://www.docker.com/products/docker-desktop/), clone the repo, put the `.env` from Victor in the `Flowsaic` folder (or `Flowsaic\backend`), then:

1. Double-click **`setup.cmd`** once. It checks your tools (installs uv if missing, starts Docker), fixes common `.env` mistakes (a `.env.txt` name, a "Unicode" save, a missing `DATABASE_URL`), starts the database, installs everything including Chromium, and loads all the data. It asks whether to load this term's course schedule live from mySAU (a browser opens and you sign in); if that fails it says why and uses the saved schedule. Safe to run again; it asks before resetting the sign-in users.
2. Double-click **`start.cmd`** any time to run Flowsaic. It starts Docker and the database if needed, runs the server and opens http://127.0.0.1:8000/ (sign in as 1–4, any password). If Flowsaic is already running it just opens the page. `start.cmd -Port 8001` uses another port.

The scripts are `backend/setup.ps1` and `backend/start.ps1`; `db/scripts/status.py` prints what's loaded. Settings are read from `backend/.env` and the repo-root `.env` (backend wins); a missing `DATABASE_URL` gives a plain message saying where to put the file.

**By hand** (any OS; on Mac/Linux write `../db/scripts/...` instead of `..\db\scripts\...`). You need Git, Docker Desktop (running) and [uv](https://docs.astral.sh/uv/). Every laptop has its own database, filled once with these steps:

1. **`.env`:** put it in `backend/.env` or the repo root (start from `backend/.env.example`; get the Gemini key from Victor). Never commit it.
2. **Database:** `docker compose up -d` from the repo root starts Postgres 17 (pgvector image) on host port **5433** (5432 is often taken by a local Postgres).
3. **Backend:** from `backend/`: `uv sync`, then `uv run alembic upgrade head` (builds the tables; Alembic lives in `backend/alembic/`), then `uv run playwright install chromium` once (for mySAU).
4. **This term's course schedule, live from mySAU:** `uv run python ..\db\scripts\connect_mysau.py`. A Chromium window opens; sign in to mySAU yourself (Microsoft + Duo). It exports the live course schedule and loads it; no Flowsaic student is needed and nothing about your login is stored. If mySAU is down, `uv run python ..\db\scripts\import_sections.py` loads the committed Nov 16 file (`data/sections_spring_2027.csv`) instead.
5. **Course descriptions, prereqs and degree maps** (no requests to SAU; everything comes from files in the repo):
   - `uv run python ..\db\scripts\scrape_course_info.py`: loads `data/course_info.csv` and embeds the ~1,868 descriptions for RAG (a few minutes and a few cents on the Gemini key; reruns only embed changed text).
   - `uv run python ..\db\scripts\scrape_degree_maps.py --offline`: builds all 139 degree plans from the saved pages in `data/raw/degree_maps/`, in seconds.
6. **Sign-in users:** `uv run python ..\db\scripts\seed_demo.py` (after steps 4–5): users 1–3 (demo students) and 4 (new student).
7. **Check and run:** `uv run python ..\db\scripts\check_db.py`, `uv run pytest`, then `uv run fastapi dev app/main.py` and open http://127.0.0.1:8000/ (sign in as 1–4, any password). API docs at `/docs`.

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

Eleven contract tables, plus `doc_chunks` (RAG), `student_requirements` and `refresh_runs` (migration `0002_data_retrieval`, Nov 17). Each section's meeting time lives on the section row, because one export row is one section with one time. Labs (`002L`) are their own sections.

| Table | Fields | Notes |
| --- | --- | --- |
| `terms` | id, code, name, is_current_registration | e.g. Spring 2027. `is_current_registration` = the term the latest schedule export covers |
| `courses` | id, code, title, department, credits, description, other_requirements | `code` like `CSCI 3103`; description from SAU catalog. `department` and `credits` come from the sections export, so they are `null` for courses not offered this term |
| `course_prereqs` | course_code, requires_code, option_group | One row per prereq. Rows sharing an `option_group` are alternatives (any one counts). Empty = no prereqs |
| `sections` | id, course_id, term_id, section_number, instructor, location, building, room, days, start_time, end_time, division, enrolled, capacity, active | Blank days/times = online or TBA. Blank instructor = "Staff". `start_time`/`end_time` are Postgres `time` columns; the API formats them as `HH:MM`. One row per (course, term, section number). A section missing from a newer export is set `active=false`, **never deleted**, because saved schedules point at it |
| `degree_plans` | id, name, catalog_year, total_hours, source_url, scraped_at | e.g. "Computer Science, BS", "2026-2027". `catalog_year` is text. `source_url`/`scraped_at` set by the degree map scraper |
| `requirement_groups` | id, degree_plan_id, parent_id, name, rule, hours_required, sort_order, note | Tree of requirements. `note` = rules that are not a course list ("may only include one course in Art"), shown, not enforced |
| `requirement_courses` | group_id, course_code | Courses that count toward a group |
| `students` | id, name, email, password, degree_plan_id, classification, major, catalog_year, has_hold, total_hours_earned, total_hours_needed, audit_refreshed_at | Demo accounts only. Plain demo password is fine for semester 1. The audit fields come from mySAU connect; `has_hold` is a yes/no only |
| `completed_courses` | id, student_id, course_code, status, grade, credits, term, source, requirement_name | `status` = `completed` or `in_progress`. `source` = `audit`, `self_reported` or `manual` (default). Key is `id`: one course can appear on several audit lines (two requirements, a retake, or also self-reported). `requirement_name` is null for nonapplied coursework |
| `student_requirements` | id, student_id, name, parent_name, status, rule, hours_earned, hours_required, course_options, note, sort_order | A connected student's audit blocks. `status` = `met`, `not_met`, `in_progress`; `rule` = `all` or `choose_hours`; `course_options` (text[]) = the "Select N hours from…" list or the required courses |
| `refresh_runs` | id, kind, status, started_at, finished_at, rows_changed, error, student_id | One row per scrape or connect. `kind` = `course_info`, `degree_maps`, `sections`, `audit`; `status` = `running`, `ok`, `failed`. `error` is a short message of our own, never page content. `student_id` null for public runs |
| `schedules` | id, student_id, term_id, name, source, created_at | source = `manual` or `ai` |
| `schedule_sections` | schedule_id, section_id | |

`course_code` columns are plain text, not foreign keys, so a degree plan can list courses not offered this term.

Computed on read, never stored: `seats_open = capacity - enrolled` (floor 0), and degree progress.

**Degree progress (`app/progress.py`, built Nov 17):** the student context `GET /me/progress` returns and Flow will be given.
- Source: the student's mySAU audit if connected (its statuses are used as is), otherwise their public degree map.
- Passed = completed with a grade other than F or W. In progress shows as `in_progress`, never `met`, but counts for prereqs.
- `all` / `choose_hours` as in Degree plan format. A course used by one choose group isn't reused by another (no ENGL 2223 for both World Lit and Fine Arts).
- Elective lines in notes ("12 hours of upper-level Psychology electives") are parsed (`parse_electives`, subject words → prefixes in `SUBJECT_PREFIXES`, upper-level = 3000–4000). Taken courses no listed requirement used fill them, narrowest first. Lines it can't read stay notes. A group with nothing trackable ("an approved minor") is `not_tracked`, never `met`.
- **Can take** = offered in the current registration term, not passed or in progress, undergraduate, prereqs met (every prereq group has an option passed or in progress). Kinds: `required`, `choice`, `elective` (subject electives list real offered courses; unrestricted ones aren't enumerated). A course the plan lists by name is never also an elective. Needed courses blocked by a prereq are listed separately.

**Which degree plan is a student's? (decided Nov 17)** For a student who has connected mySAU, the audit (`student_requirements`) **is** their degree plan: it is for their own catalog year (for example 2023) and already says what is met, what is left, and the course options for each unmet requirement. Public degree maps (`degree_plans`) are the fallback for students who have not connected, for demo students, and for "what if I switched majors" questions.

## Degree plan format

Public degree maps are scraped (Nov 17): `scrape_degree_maps.py` loads every undergraduate program, minor included, straight into these tables (see Data sources). The hand-entered JSON format below (`/data/degree_plans/`, `load_degree_plans.py`, not written yet) is only needed for a plan the scraper can't read.

A plan is a tree of requirement groups. Each group has one rule:
- `all`: every listed course and child group must be done.
- `choose_hours`: completed listed courses must add up to `hours_required`.

A parent group is met when its own rule is met and all its children are met. See the contract for a full JSON example. Not handled in semester 1: "only one Art and one Music course," residency hours, upper-level hour totals, transfer substitutions (shown as plain text notes only).

## Data loading

Scripts in `/db/scripts/`, run from `backend/` (`uv run python ..\db\scripts\<name>.py`). Re-running updates rows instead of duplicating them. Scripts 1 and 2 work in either order; 3–5 come after them. **Built so far (Nov 17): 1, 2, 4 and 5, plus `search.py` and the data retrieval scripts (see Data sources).** 3 is not written yet (the scraper covers every program). The import logic lives in `backend/app/` (`mysau/sections_import.py`, `course_load.py`, `course_embed.py`, `demo_seed.py`) so the scripts and the API share it; the scripts are thin wrappers.

1. `import_sections.py [file]`: a course schedule export → terms, courses, sections. Same importer as mySAU connect. **Loaded Nov 17 from a live mySAU export: 1,343 sections (10 older ones set inactive), 869 courses offered.**
   - Reads both mySAU's raw export (no header row, unquoted commas inside titles and departments, labs written `001  L`) and a CSV with a header row like `/data/sections_spring_2027.csv` (the hand-cleaned Nov 16 file). Columns, in this order: `course_section, title, term, department, start_time, end_time, days, campus, building, room, instructor, level, credits, enrolled, capacity, concurrent`.
   - A section of the file's term that is missing from the file is set `active=false`. The file's term becomes `terms.is_current_registration`.
   - Normalize times (`09:00:AM` → `09:00`, `01:30:PM` → `13:30`) and days (`M W F` → `MWF`). Blank times/days = online or TBA. `level` = division (UG/GR). `credits` like `3.0` → integer.
   - Older exports were an HTML table with an `.xls` name. The importer refuses those with a clear message; convert one with `pd.read_html(path)[0]` first if you ever need it.
   - Last token of the course code is the section (`001`, `002L`, `001H`); the rest is the course code. Insert a missing space (`SCM6003` → `SCM 6003`).
   - Skip the Concurrent column. Bad rows are printed and skipped, never guessed.
   - **One meeting time per section** (decided Nov 16). The export lists 86 sections on 2–3 rows, one per meeting time (lecture plus an evening exam slot, or an in-person row plus a "Hybrid Course" row). The importer loads the row with the most meeting days (ties: first in the file) and prints the other rows as "extra meeting time, not loaded" (87 on Nov 16, 89 in the Nov 17 export). The checker can't see those extra times; see Open questions.
   - Sections whose title starts with `CANCELED` (5 rows) are printed and skipped.
   - A course already in `courses` only gets `department` and `credits` filled in; the catalog title wins. A course missing from the catalog gets a minimal row and is reported as having no description (85 on Nov 16, all graduate level; 2 more on Nov 17: EDFN 7303, KINE 6813).
   - Term `code` is SAU's export text as is (`2026-2027 - Spring`); `name` is `Spring 2027`.
   - 37 sections have days but no times (mostly high-school concurrent sections). They load with days and blank times.
2. `load_course_info.py`: `/data/course_info.csv`. **Done Nov 16: 1,878 courses** from SAU's public 2026–27 catalog (raw scrape + rebuild script in `/data/raw/`; re-run `python build_course_info.py` to regenerate without scraping again). `scrape_course_info.py` (Nov 17) rebuilds the same CSV with the same rules, loads it and re-embeds only changed courses.
   - Columns: `code, title, description, prereqs, other_requirements, prereq_text, coreqs, coreq_text, needs_review`.
   - `prereqs`: `;` = all required, `|` = any one of these. Example: `CHEM 3103;MATH 1023|MATH 1053` = CHEM 3103 AND (MATH 1023 OR MATH 1053). Load each `|` group with a shared `option_group`. Every `;` group gets a number starting at 1, so a single required course is a group of one. **Loaded Nov 16: 1,025 prereq rows across 603 courses.** Re-running replaces a course's prereq rows, so a fixed CSV fixes the table.
   - **Known data problem:** 15 courses mix `;` and `|` in a way that encodes lecture/lab pairs wrongly (e.g. BIOL 2061: `CHEM 1013;CHEM 1011|CHEM 1023;CHEM 1021` loads as CHEM 1013 AND (CHEM 1011 OR CHEM 1023) AND CHEM 1021, but the catalog means one lecture+lab pair OR the other). The checker would block wrongly on these; 8 are offered this term. Fix in the CSV, not the loader.
   - `other_requirements` (instructor permission, standing, admission): stored, **not enforced** in semester 1.
   - `needs_review` (120 rows, also in `/data/course_info_needs_review.csv`): prereqs too complex to parse are left **blank** so the checker never blocks wrongly; 10 courses have no description because SAU's own pages are broken. Fix by hand only the ones on demo plans.
   - **Careful:** `scrape_course_info.py` rewrites `course_info.csv` from the raw catalog text, so a hand fix in the CSV is lost the next time it runs. See Open questions.
3. `load_degree_plans.py`: every JSON file in `/data/degree_plans/`.
4. `seed_demo.py` (after the degree maps): 3 fake students on different plans and stages, with completed and in-progress courses (`source='manual'`). **Built Nov 17.** All use the password `flowsaic-demo` and `@demo.flowsaic.test` emails. Data in `backend/app/demo_seed.py`; each is built around real Spring 2027 sections so the demo shows real results. Classification follows earned hours (under 30 freshman, 30–59 sophomore, 60–89 junior, 90+ senior); credits come from the last digit of the course number. "In progress" = Fall 2026.
   - **Alex Rivera, Computer Science, BS, junior (64 hours, incl. MATH 1023 concurrent credit so MATH 3043 is open):** the main demo. CSCI 4203 and MATH 3043-002 overlap (MW 14:10), MATH 3043-001 is full, CSCI 4932 needs CSCI 4922 (missing), CSCI 3143's prereq CSCI 3213 is in progress, CSCI 3103 is already completed.
   - **Jordan Brooks, Business Administration: General Business, BBA, freshman (3 hours, first semester in progress):** MGMT 2003 needs ENGL 1123 (missing even if both are on one schedule); ACCT 2003-001 and ECON 2103-001 overlap (MWF 09:00).
   - **Sam Okafor, Psychology, BS, senior (95 hours):** close to graduating; failed PSYC 3183 (an `F` row) and is retaking it this fall, so progress and the checker must not count the F. PSYC 4053's only section is full.
   - **New Student (`new.student@demo.flowsaic.test`, user 4):** no plan, no courses. Fills their own record with Connect mySAU (the real schedule + their own audit). **Every seed run resets them to empty**, which also removes a real audit before a database dump is shared.
5. `embed_course_info.py` (RAG, after 1–2): chunks and embeds course descriptions into `doc_chunks`. See RAG. **Done Nov 16: 1,868 chunks.** It skips courses whose `doc_chunks.content_hash` (sha256 of the chunk text) is unchanged, so a re-run resumes and costs nothing.
6. `search.py "query"`: test tool. Embeds the query and prints the top 8 courses (code, title, cosine distance).

## Data sources and refresh (Nov 17)

Flowsaic fetches its own data instead of anyone loading files by hand.

| Data | Source | Login? | How | Refreshes |
| --- | --- | --- | --- | --- |
| Course descriptions + prereqs | catalog.saumag.edu course pages (`preview_course_nopop.php`, catalog `catoid=10` = 2026–27) | No | HTTP + BeautifulSoup, `scrape_course_info.py` | Reuses the saved raw text by default (no requests); crawls only when `COURSE_INFO_CRAWL=true` (a new catalog year) |
| Degree maps (every undergraduate program and minor) | www.saumag.edu/academics/program/… pages + the general education page | No | HTTP + BeautifulSoup, `scrape_degree_maps.py` | Startup (if older than 7 days) and `POST /data/refresh/public` |
| Sections (course schedule) | mySAU → Course Schedule → Export → CSV | Yes (student signs in) | Playwright, `connect_mysau.py` / `POST /connect/mysau` | When a student clicks "Connect mySAU" |
| Student degree audit | mySAU → Student → Academics → View All Details → Recalculate → Printable Degree Audit (PDF) | Yes (student signs in) | Playwright + pdfplumber, same | Same |

- **catalog.saumag.edu is behind an AWS WAF bot challenge** on its list pages (`content.php`) and program pages (`preview_program.php`). We never try to get past it: no headless-browser workaround. Course detail pages answer plain HTTP. Its robots.txt asks for **120 s between requests** and disallows `/ajax/`, and the polite client (`backend/app/catalog/http.py`) obeys both. That is why course text is crawled only once a catalog year (~63 hours for ~1,900 pages).
- **Degree maps come from SAU's main site**, whose program pages copy the catalog curriculum and link back to it ("Degree Plan 2026-2027" → catalog poid). Only pages linking to the configured `catoid` are loaded; plan names come from the catalog's own list (`data/raw/degree_maps/programs_list.html`, saved once from a browser). One page every 30 s (`DEGREE_MAPS_DELAY_SECONDS`), ~150 pages. Rules: a course block = `all`; "Select N hours from…" = `choose_hours`; other text = `note`; lecture+lab "one of these combinations" = `choose_hours` with the pairs in the note (flagged). The shared gen ed core (35 hours) is copied under each plan's "General Education" block minus the areas the program says its major covers. Programs that don't parse cleanly go to `data/degree_maps_needs_review.csv` and load anyway. The parsed parts of each page are saved under `data/raw/degree_maps/` so `--offline` rebuilds without requests.
- **Settings** (all optional in `backend/.env`, defaults in `app/config.py`): `CATALOG_CATOID` (one place for the catalog year), `CATALOG_MIN_DELAY_SECONDS`, `COURSE_INFO_CRAWL`, `DEGREE_MAPS_DELAY_SECONDS`, `PUBLIC_REFRESH_ON_STARTUP`, `PUBLIC_REFRESH_MAX_AGE_DAYS`.
- **Startup never waits:** the check runs in a background thread. Runs cut off by a restart are marked `failed` at the next startup. Partial CLI runs (`--only`, `--limit`) are not recorded, so they never look like a fresh refresh.

How to run each one (from `backend/`):

```
uv run python ..\db\scripts\scrape_course_info.py                 # rebuild + load + re-embed changed (no requests)
uv run python ..\db\scripts\scrape_course_info.py --limit 5       # also fetch 5 stale course pages
uv run python ..\db\scripts\scrape_degree_maps.py                 # every program, ~1+ hour
uv run python ..\db\scripts\scrape_degree_maps.py --only computer-science
uv run python ..\db\scripts\scrape_degree_maps.py --offline       # re-parse saved pages, no requests
uv run python ..\db\scripts\scrape_degree_maps.py --show "Computer Science, BS"
uv run python ..\db\scripts\connect_mysau.py                         # live course schedule only (you sign in)
uv run python ..\db\scripts\connect_mysau.py --student-id <uuid> --fetch sections audit
uv run python ..\db\scripts\import_sections.py <export.csv>       # load a schedule export by hand
```

Endpoints for this (added by prompt 2, **not among the contract's sixteen yet**, no session check yet):

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/data/refresh/public` | | 202 `{ runs: [{ id, kind }] }` (degree_maps, then course_info, in the background); 409 `refresh_already_running` |
| GET | `/data/refresh/{id}` | | The `refresh_runs` row; 404 `refresh_run_not_found` |
| POST | `/connect/mysau` | `{ student_id, fetch: ["sections", "audit"] }` | 202 `{ runs: [{ id, kind }] }`; 404 `student_not_found`; 409 `connect_already_running` |
| POST | `/me/connect-mysau` | `{ fetch }` (optional, default both) | Same as above for the **signed-in** student; 401 `not_authenticated`. Used by the prototype home page |
| GET | `/me/audit` | | `{ refreshed_at, requirements: [...] }`: the student's `student_requirements` (their mySAU audit blocks). Empty list if never connected |

### mySAU connect

- A **headed** Chromium window opens on the machine running the backend (fine for the demo laptop; a hosting problem for semester 2). The student signs in themselves (Microsoft + Duo); the script waits up to 5 minutes and never types into the sign-in. "Signed in" = back on my.saumag.edu with the Login button gone.
- The audit attaches to an **existing** Flowsaic student (`student_id`). It never creates a student and never changes name, email or password. It replaces only that student's `source='audit'` course rows and their `student_requirements`, in one transaction.
- Selectors are role/text selectors from a codegen recording (Nov 17), not CSS positions. Re-record with `uv run playwright codegen https://my.saumag.edu/ICS/` if mySAU changes (turn recording off while signing in).

**Privacy rules (non-negotiable):**
- Never store, log or print a mySAU password, cookie, token or Playwright `storage_state`. Fresh browser context every run, closed in `finally`. No persistent profile. Downloads are refused by the context.
- Playwright tracing, video and screenshots stay **off** for mySAU pages. A test fails if the connect code ever calls them.
- Never log page HTML or audit text. Errors in `refresh_runs` are our own step codes plus the error type (`audit_export failed (TimeoutError)`).
- The audit PDF and the schedule CSV are captured from the network response **in memory only**; the browser is shown a "received" page instead of a download. Never write the audit PDF to disk and never commit any PDF (`*.pdf` and `data/private/` are gitignored).
- From the audit, the header is discarded: name, ID number, address, phones, advisor, GPA. Holds become only `has_hold` (a hold's name can reveal a balance owed). Kept: major, catalog year, classification, course lines (code, grade, credits, term, status), requirement statuses (name, met / not met / in progress, hours) and total hours earned/needed.
- Tests use a **fake** audit only. Never put a real audit in tests or fixtures.

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

**Built Nov 17 (`app/checker.py`, `POST /schedules/check`).** Details:
- `missing_prereq`: every prereq group needs one option passed (not F/W) or in progress. A course in the same schedule doesn't count. Message: "MGMT 2003 needs ENGL 1113 and ENGL 1123 (passed or in progress)".
- `already_completed`: passed courses only (in progress isn't completed).
- `not_on_plan`: not listed in the student's plan and not matching one of its subject/level electives (for a connected student: not in any audit requirement's course options). Says "(it would count as a general elective)" when the plan has unrestricted electives. No warning for a student with no plan yet.
- `over_credit_limit`: each course counted once; exactly 18 is fine.
- Errors: 404 `section_not_found` (unknown or inactive section), 422 `section_not_in_term`. Duplicate IDs in the request are dropped.

**Solver (`app/solver.py`, built Nov 17).** `find_schedules(must, optional, constraints)` returns up to 5 section combinations (one section per course, no time overlaps), best first, plus the must courses that can't be placed and why. Optional courses are added best first until the credits reach the target. Hard constraints: unavailable blocks, earliest start, latest end, days off, instructors to avoid, open seats only, no online. Soft (ranking): preferred time of day, lunch, preferred instructors, fewer days on campus, avoiding full sections. A tool for Flow; every result still goes through the checker.

Each item: `{ "code": "time_overlap", "section_ids": ["...", "..."], "message": "CSCI 3103 and MATH 2753 overlap on MW 10:00" }`. The front end shows `message` as is.

## Flow, the AI advisor (decided Nov 17)

Flow is Flowsaic's AI advisor (Gemini behind it), on Andy's AI Advisor page. It's a conversation, not a form: it explains degree progress, finds courses and electives that fit what the student wants, builds and adjusts schedules around constraints, and asks for what it needs ("how many credits?", "any times you can't do?"). Endpoint: `POST /ai/advisor` `{ message, history }` → `{ reply, proposals }` (each proposal is a checked schedule). **Built Nov 17** (`app/advisor.py`, `app/routers/ai.py`).

- **What Flow knows:** the student's record from SQL (classification, major, catalog year, hours, completed and in-progress courses with F/W not counting, what's still needed from the audit or the degree map, and elective candidates found by code: subject, level, offered this term, prereqs met), plus the last 20 messages (sent by the front end).
- **Tools Flow calls (Gemini function calling), all scoped to the signed-in student:** `get_my_progress`, `find_courses` (RAG over courses the student can take), `get_sections`, `check_schedule` (the checker), `find_schedules` (a solver that returns section combinations meeting constraints), `propose_schedule` (a checked schedule card).
- **Code does the exact work** (eligibility, counting, time conflicts, combinations); Flow chooses, explains and talks. That's what keeps a fast model reliable.
- Every schedule Flow shows has been through the checker; conflicts are shown, never hidden. **Flow never saves**: the schedule card has a Save button the student clicks.
- **Personal, without sharing identity:** Flow greets and addresses the student by first name. The name is **never sent to Gemini**: Flow writes `{first_name}` and the backend fills it in before the reply is shown.
- **How the loop works:** up to 10 Gemini calls per message (tools disabled on the last); two steps before the end Flow is told to propose and wrap up; an empty answer gets one plain retry. Tool results go back with role `user` (the API rejects `tool`). Sections are referred to by labels like `CSCI 4203-001`, never IDs. A reply takes ~10–30 s depending on tool rounds.
- **Front end:** keep the conversation and send it back as `history` (last 20). For Flow's turns send the reply's `memory`, not `reply`: `memory` keeps `{first_name}` and lists the schedules shown. Each `proposals[]` item is a checked schedule (`term_id`, `section_ids`, sections, credits, conflicts, warnings); its Save button calls `POST /schedules` with `source: "ai"` (blocked while it has conflicts).
- Errors: 503 `gemini_model_not_set`, 502 `ai_unavailable`.
- **Guardrails (tested Nov 17 with messy, real-student prompts):** Flow looks a course up before saying it is or isn't offered (`get_course` also returns related courses, e.g. the whole Senior Project sequence, each with offered/blocked status); says it doesn't know anything outside Flowsaic's data (no made-up restaurants, dates or policies); asks one question when a new constraint is vague ("I have a job") instead of guessing; says when a swapped-out course is still required; never claims to register or save.

## AI suggest (Gemini, the Create Schedule form)

Uses the same engine as Flow, for a one-shot form instead of a conversation. **Built Nov 17** (`POST /ai/suggest`): the preferences become a request to Flow in suggest mode (no questions, exactly one `propose_schedule`); the response is that schedule. Only the current registration term is supported (`term_id` for another term → 422 `term_not_supported`).

1. Student fills the preferences form and hits Suggest.
2. Backend gathers remaining requirements, completed/in-progress courses, and eligible sections for the term (on the plan, not completed, prereqs met). This keeps the prompt small.
3. Backend sends Gemini the preferences, requirements and eligible sections (plus RAG context, see below) and asks for JSON only: `{ "section_ids": [...], "explanation": "..." }`.
4. Backend runs the checker on the result.
5. On conflicts, send them back to Gemini and ask for a fix. Maximum 3 tries.
6. Return the schedule, explanation and warnings. If all 3 tries fail, return the best attempt with its conflicts shown.

Preferences are all optional: `term_id`, `target_credits`, `unavailable` (list of `{days, start, end}`), `preferred_time` (`morning` / `afternoon` / `evening` / blank), `lunch`, `preferred_instructors`, `avoid_instructors`, `notes`. Gemini treats preferences as wishes and checker rules as hard limits.

- Model name and key come from `.env` (`GEMINI_MODEL`, `GEMINI_API_KEY`), so switching models is a one-line change.
- **Set a spending cap in the Google account before the first call.**
- Send the LLM course data and preferences only. Never student names, emails or IDs; use the student's degree plan and course codes. (Flow's `{first_name}` is filled in by the backend after Gemini replies.)
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

Twenty-two endpoints in contract v2: the sixteen below, `POST /ai/advisor` (Flow, above), and the five data/connect endpoints listed under Data sources (`/me/audit`, `/me/connect-mysau`, `/connect/mysau`, `/data/refresh/public`, `/data/refresh/{id}`). Everything except login, `/data/*` and `/connect/mysau` needs the session cookie and acts on the logged-in student.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{ email, password }` | Student; sets session cookie |
| POST | `/auth/logout` | | 204 |
| GET | `/me` | | Student name, plan, classification |
| GET | `/me/progress` | | `{ source, plan, term, hours, requirements (tree: status met/in_progress/not_met/not_tracked, hours, courses, electives), can_take, blocked, open_electives }` |
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
| POST | `/ai/advisor` | `{ message, history }` | `{ reply, proposals }` (Flow; each proposal is a checked schedule) |

**Built (Nov 17):** `POST /auth/login`, `POST /auth/logout`, `GET /me`, `GET /me/progress`, `GET /me/completed-courses` (also returns title, grade, credits, term, source, requirement_name), `POST /schedules/check`, `GET/POST /schedules`, `GET/PUT/DELETE /schedules/{id}`, `POST /ai/advisor`, `POST /ai/suggest`.

**Saving schedules (built Nov 17):** `POST` and `PUT /schedules` run the checker first; conflicts block saving with 422 `{ "error": "schedule_has_conflicts", "conflicts": [...] }`, warnings don't. Another student's schedule is 404 `schedule_not_found`. `GET /schedules/{id}` returns the sections (with `active`; a section dropped from a later export stays, marked inactive) plus a fresh check.

**Prototype login (Nov 17, temporary):** `email` also accepts the usernames `1`–`4` (1 Alex, 2 Jordan, 3 Sam, 4 New Student; see Data loading) and **the password is not checked**. Sessions are a random token in an HttpOnly cookie, kept in the server's memory (a restart signs everyone out). Errors: 401 `invalid_credentials`, 401 `not_authenticated`. Real passwords and server-side sessions are semester 2.

**Prototype pages (Nov 17):** the backend serves a sign-in page at `/` (`backend/app/static/login.html`). Signing in opens the tabbed test page at `/dev` (`dev.html`): **My profile** (with Saved schedules), **AI Advisor** (Flow, with schedule cards and Save; it replaced the old Chat tab, whose `/dev/chat` endpoint is no longer used by the page), **Schedule lab** (try the checker and the solver; its helper endpoints `GET /dev/lab/sections` and `POST /dev/lab/solve` are test-page only, not contract), Search, Browse, Database. `/dev` sends you back to `/` when you're not signed in; `/home` redirects to `/dev`. This lets the flow be tested before the React front end is wired up. My profile only calls the endpoints above: users 1–3 show their demo record; user 4 starts empty and has a **Connect mySAU** button. Demo students don't get the button, so a real audit never mixes into a fake student.

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
- Contract: version 2 (Nov 17) written by Victor to match what's built plus Flow; needs the team's review in the group chat.
- Backend (Nov 17): repo now at `Documents\GitHub\Flowsaic`. Working: `GET /health`, `/dev`, settings, all models, migrations `0001` + `0002_data_retrieval`, the loaders, embeddings, `search.py`, the public scrapers (course info, degree maps with gen ed), `POST /data/refresh/public` + `GET /data/refresh/{id}` + background refresh on startup, and mySAU connect (`POST /connect/mysau`, CLI) with the audit parser, both tested live once, the full degree map scrape, `seed_demo.py` (3 demo students + user 4), prototype login (`/auth/login`, `/auth/logout`, `/me`, `/me/completed-courses`, `/me/audit`, `/me/connect-mysau`) and the sign-in page + the My profile tab on `/dev`. `/me/progress` with the progress tree and "You can take" on My profile. The schedule checker (`POST /schedules/check`) and the solver, with the Schedule lab tab. Flow (`/ai/advisor`, live-tested with Alex and Sam), AI suggest, and saving schedules (`/schedules`), with the AI Advisor tab and Saved schedules. 194 tests pass. Not built yet: the catalog endpoints (`/terms`, `/courses`, `/courses/{id}`), `PUT /me/completed-courses`, CORS for the React dev server, `load_degree_plans.py`, the Course Search fallback. Next: catalog endpoints and CORS so Andy can wire up the React app.
- Course data: `/data/course_info.csv` done (1,878 courses, Nov 16). `data/raw/degree_maps/` holds the saved program pages. Not committed yet.
- Database (Victor, Nov 17): Postgres 17 + pgvector 0.8.7 in Docker on port 5433. Loaded: 1 term (Spring 2027, current registration), 1,965 courses, 1,025 prereq rows, 1,353 sections (1,343 active), 1,868 embedded chunks, 139 degree plans (every undergraduate program and minor on the 2026–27 catalog; 1,726 requirement groups), 3 demo students (`seed_demo.py`). The live mySAU test student was deleted Nov 17, so no real audit is in the database. Empty: schedules.
- Front end: _fill in_

## Decisions log

- **Nov 16:** the earlier database/RAG scripts (`documents`/`chunks` tables, keyword search, `ingest.py`, `api.py`, `load_courses.py`) are **replaced** by the contract schema. Don't use or copy them. Victor builds the new schema and migrations.
- **Nov 16:** schema built. Additions beyond the contract's field lists, which the contract doc still needs: `courses.other_requirements` (nullable text), `sections.start_time`/`end_time` as `time` columns, `degree_plans.catalog_year` as text, and the `doc_chunks` shape in the RAG section.
- **Nov 16:** sections importer keeps one meeting time per section and skips canceled sections (see Data loading).
- **Nov 16:** embedding text formats for `gemini-embedding-2` are fixed (see RAG). Changing them means re-embedding every row.
- **Nov 16:** local database runs on host port 5433, bound to this laptop only (`127.0.0.1` and `::1`). Its dev-only password is in `docker-compose.yml`; it protects fake data in a local container and must never be reused.
- **Nov 17: automated data retrieval.** Flowsaic fetches its own data: public scrapers for course descriptions and degree maps, and a student-run mySAU connect for the course schedule and the degree audit (see Data sources). Migration `0002_data_retrieval` adds the columns and the `student_requirements` and `refresh_runs` tables. `completed_courses` now has an `id` key because one course can appear on several audit lines.
- **Nov 17: Playwright connect, no stored credentials.** The student signs in themselves in a visible browser; the script never sees or stores a password, cookie, token or session, and files are captured in memory. This is the one place Flowsaic works behind a login, and only with the student at the keyboard.
- **Nov 17: audit header discarded.** Name, ID, address, phones, advisor and GPA are never stored; holds are a yes/no only. For a connected student the audit is their degree plan; public degree maps are the fallback.
- **Nov 17: catalog bot protection is respected.** catalog.saumag.edu's list and program pages are behind an AWS WAF challenge; we don't get around it. Course text is reused from the Nov 16 scrape and re-crawled (120 s/page, robots.txt) only for a new catalog year. Degree maps come from www.saumag.edu's open program pages instead.

## Open questions (don't build around these yet)

- **Sections with more than one meeting time.** 86 sections have 2–3 meeting times, but `sections` stores one, so the conflict checker misses 87 real meeting times. Storing them needs a meetings table, which is a contract change.
- **Mixed AND/OR prereqs.** 15 courses are encoded wrongly in `course_info.csv` (see Data loading). Decide whether to fix them by hand or blank them like the other `needs_review` rows.
- **High-school concurrent sections** (39 rows, `concurrent = Yes`) are loaded like any other section. Decide whether the catalog should hide them.
- **Hand fixes to `course_info.csv`** are overwritten whenever `scrape_course_info.py` rebuilds it. Option: a small `data/course_info_overrides.csv` applied after every rebuild.
- **Failing grades on the audit** (F, W) are stored as `completed` with their `grade`. Anything that counts completed courses (checker, progress) must look at `grade` too. Demo student Sam Okafor has such a row (PSYC 3183, F, retaken in Fall 2026).
- **Course titles from the audit** aren't stored (no column); the title comes from `courses` by code. Transfer lines are stored as the SAU course they count as (e.g. `ENGL1013 … (ENGL1113)` → ENGL 1113).
- **Course Search fallback** for a failed schedule export isn't built: no recorded selectors yet. Record that path with codegen if we need it.
- **Degree map data quirks:** SAU's gen ed page lists MATH 2124 Applied Calculus while the CS major lists MATH 2125; one page likely has a typo. A program note that names a required course (e.g. AGEC 2073 for Poultry Science) is loaded on the gen ed block and flagged, because the page doesn't say which area it fills.
- **Electives in a real audit:** how mySAU lists elective options (a list, a pattern like `CSCI 3XXX`, or text) is unknown until the next Connect mySAU as user 4.

## Semester 2 (parked, don't build before Dec 7)

Kept here so these aren't lost. They come back when the real product starts:
- **Multi-tenancy:** `institution_id` on every table, taken from the session only; cross-institution access returns 404.
- **Real auth:** server-side sessions in HttpOnly/Secure/SameSite cookies; argon2/bcrypt hashing; login rate limits; roles `student` / `advisor` / `admin`, default-deny.
- **Advisor side:** queue, confirm/deny matching SAU's Jenzabar approval, messaging. Status flow `draft → submitted → approved | denied`.
- **FERPA hardening:** audit log on every read/change of a student record; no personal data in logs; strip identifying info before any LLM call; check the LLM provider's no-training/retention terms; encryption at rest; HTTPS only; `/docs` off in production.
- **Jenzabar roadmap:** no access → read-only API → write access. Never use or store student credentials. The only behind-login automation is the student-run mySAU connect (Nov 17), which a real integration should replace.
- **mySAU connect hosting:** the connect browser opens on the machine running the backend. That works on the demo laptop, not on a server. Hosted, it needs a different design (a browser extension, a student-side helper, or the Jenzabar API).
- **Other:** multiple schools and branding, complex degree rules, deployment, WCAG 2.1 AA accessibility.
