# AGENTS.md — Flowsaic

Shared rules for every AI coding tool on this team and every teammate. Cursor reads this file automatically, and Claude Code reads it through `CLAUDE.md`. ChatGPT doesn't read files on its own, so paste this file into a ChatGPT Project's instructions or at the start of a chat. **If this file and your AI disagree, this file wins.**

The source of truth for scope, data and API shapes is the team's **Flowsaic Semester 1 Contract** doc, **version 2 (Nov 17, 2026)**. It replaces version 1 (Nov 11) and the old "Data & API Contracts" doc. If this file and the contract disagree, the contract wins. Fix this file.

## What changed on Nov 18 (read this first)

- **Aaron (database):** migration **`0003_student_planning`** (`backend/alembic/versions/0003_student_planning.py`) adds three tables, each keyed to `students.id` with `ON DELETE CASCADE`: `calendar_events`, `student_preferences` (one row per student) and `student_settings` (one row per student). It changes no existing table. Run `uv run alembic upgrade head` from `backend/` (`setup.cmd` and now `start.cmd` do it for you). Shapes are in Data model below.
- **Everyone (privacy rule changed):** Connect mySAU now keeps the student's **first and last name** from the audit (no middle name or initial; everything else in the header is still discarded), and **Flow (Gemini) is given the student's first name** (Victor's decision, Nov 18). The last name, email and ID still never go to Gemini. See Privacy rules and the Decisions log.
- **Andy (front end):** the React app in `/frontend` is wired to the backend (Victor did it with your OK). `App.tsx` was split into `src/pages/` (one file per page), `src/components/` (`Icon`, `SignIn`, `HeaderSearch`), `src/api/` (`client.ts` = every call, `types.ts` = backend shapes, `adapters.ts` = backend ↔ UI shapes, `errors.ts` = error code → toast text), `src/types.ts` (UI shapes) and `src/mock.ts` (everything still mock, labelled). The visual design and CSS classes are unchanged; `index.css` only gained a block at the end for new elements. The app always calls `/api/...`; Vite forwards it to the backend. `npm run build` now type-checks first (`tsc --noEmit`). See Front end below.

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
| Front end | React 19, TypeScript, Vite (no router or data libraries) | `/frontend` | Andy | Cursor / ChatGPT |
| Backend + AI (Gemini, RAG) | Python, FastAPI, Pydantic, SQLAlchemy, pytest | `/backend` | Victor | Claude Code |
| Database | Postgres (pgvector image), Alembic migrations | `/db` | Aaron, with Victor | Cursor / ChatGPT |
| Data files | SAU Excel export, degree plan JSON, course info CSV | `/data` | Aaron | Cursor / ChatGPT |

Don't change another owner's folder without telling them.

Backend entry point: `backend/app/main.py`. Run with `uv sync`, then `uv run fastapi dev app/main.py` from `backend/`. Live API docs at http://127.0.0.1:8000/docs. The backend's own pages (sign-in at `/`, then the tabbed test page at `/dev`) are a developer tool now; **the React app at http://localhost:8443/ is the product.** Front end: `npm install` once, then `npm run dev` from `frontend/` (needs [Node.js](https://nodejs.org/) LTS; the demo laptop has Node 26). Don't edit backend `.py` files while a mySAU connect is running under `fastapi dev` or `start.cmd -Dev`: the reload kills the connect (plain `start.cmd` doesn't reload).

## Run locally

**The easy way (Windows), for teammates on their own:** the step-by-step guide with a troubleshooting list is in **[README.md](README.md)**. In short: install [Git](https://git-scm.com/), clone the repo, put your `.env` in the `Flowsaic` folder (or `Flowsaic\backend`), then:

1. Double-click **`setup.cmd`** once. It checks your tools (installs uv, Node.js and Docker Desktop with winget if they're missing; after a Docker install it stops and says: restart Windows, open Docker Desktop once, run setup again), starts Docker, fixes common `.env` mistakes (a `.env.txt` name, a "Unicode" save, a missing `DATABASE_URL`), starts the database, installs everything including Chromium and the front end's packages (`npm install` in `frontend/`), and loads all the data. On an empty database it loads the saved course schedule from the repo by default (it offers live mySAU instead, which needs your own SAU sign-in); if live fails it says why and uses the saved one. It ends with a self-test (backend tests and the front end's type check, ~15 s). Safe to run again; it asks before resetting the sign-in users. Every red line says what to do next, and README.md's Troubleshooting lists the exact steps for each one: user-facing messages give directions, never "ask someone". If `GEMINI_MODEL` is missing, setup adds `gemini-3.8-flash`.
2. Double-click **`start.cmd`** any time to run Flowsaic. It starts Docker and the database if needed, brings the tables up to date (`alembic upgrade head`, so a pull with a new migration just works), runs the backend and the front end (Vite) in the same window, and opens **http://localhost:8443/** when both answer (sign in as 1–5, any password). Ctrl+C or closing the window stops both. If Flowsaic is already running it reuses it and just opens the page. It refuses to start, with a plain message, when there's no `.env` or setup never finished (no courses or sign-in users). Options: `start.cmd -Port 8001` (backend port; the front end's proxy follows it), `-FrontendPort 8444`, `-BackendOnly` (no front end; opens the backend's test page), `-NoBrowser`, `-Dev` (for editing code: the backend auto-reloads and Vite gets its own minimized window). **Plain `start.cmd` runs `fastapi run` with no auto-reload (Nov 18):** on Windows a uvicorn reload sends Ctrl+C to the whole console, which killed Vite in the same window ("Can't reach Flowsaic") and cut off a running mySAU connect. Every backend start also marks leftover `running` refresh runs `failed` ("interrupted: the server stopped"), so a cut-off connect never polls forever.

`.gitattributes` keeps `.cmd` and `.ps1` files on Windows line endings in every clone (cmd.exe can misread Unix ones). The scripts must stay plain ASCII: Windows PowerShell 5.1 reads a UTF-8 file without a BOM as ANSI. All clones of the repo on one laptop share one database container (`docker-compose.yml` pins the project name `flowsaic`), so a second clone in a folder with another name reuses it instead of colliding. Setup also renames a `.env` that Windows saved as `env`, `env.txt` or `.env.txt`. The scripts are `backend/setup.ps1` and `backend/start.ps1`; `db/scripts/status.py` prints what's loaded. Settings are read from `backend/.env` and the repo-root `.env` (backend wins); a missing `DATABASE_URL` gives a plain message saying where to put the file.

**By hand** (any OS; on Mac/Linux write `../db/scripts/...` instead of `..\db\scripts\...`). You need Git, Docker Desktop (running), [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org/) LTS. Every laptop has its own database, filled once with these steps:

1. **`.env`:** put it in `backend/.env` or the repo root (start from `backend/.env.example`; a free Gemini key comes from https://aistudio.google.com/apikey, and `GEMINI_MODEL=gemini-3.8-flash` is the tested model). Never commit it.
2. **Database:** `docker compose up -d` from the repo root starts Postgres 17 (pgvector image) on host port **5433** (5432 is often taken by a local Postgres).
3. **Backend:** from `backend/`: `uv sync`, then `uv run alembic upgrade head` (builds the tables; Alembic lives in `backend/alembic/`), then `uv run playwright install chromium` once (for mySAU).
4. **This term's course schedule, live from mySAU:** `uv run python ..\db\scripts\connect_mysau.py`. A Chromium window opens; sign in to mySAU yourself (Microsoft + Duo). It exports the live course schedule and loads it; no Flowsaic student is needed and nothing about your login is stored. If mySAU is down, `uv run python ..\db\scripts\import_sections.py` loads the committed Nov 16 file (`data/sections_spring_2027.csv`) instead.
5. **Course descriptions, prereqs and degree maps** (no requests to SAU; everything comes from files in the repo):
   - `uv run python ..\db\scripts\scrape_course_info.py`: loads `data/course_info.csv` and embeds the ~1,868 descriptions for RAG (a few minutes and a few cents on the Gemini key; reruns only embed changed text).
   - `uv run python ..\db\scripts\scrape_degree_maps.py --offline`: builds all 139 degree plans from the saved pages in `data/raw/degree_maps/`, in seconds.
6. **Sign-in users:** `uv run python ..\db\scripts\seed_demo.py` (after steps 4–5): users 1–3 (demo students), 4 (returning student, keeps its mySAU data) and 5 (new student, emptied every startup and sign-in/out).
7. **Check and run:** `uv run python ..\db\scripts\check_db.py`, `uv run pytest`, then `uv run fastapi dev app/main.py`. API docs at http://127.0.0.1:8000/docs.
8. **Front end:** from `frontend/`: `npm install` once, then `npm run dev` and open **http://localhost:8443/** (sign in as 1–5, any password). `npm run build` type-checks and builds. If the backend runs on another port, set `BACKEND_URL` (e.g. `http://127.0.0.1:8001`) before `npm run dev`.

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
9. **CORS:** allow only the React dev server origin, never `*`. Origins come from `FRONTEND_ORIGINS` (comma-separated; default `http://localhost:8443,http://127.0.0.1:8443`, so nobody has to edit `.env`); a `*` in it is dropped. In practice the browser never needs CORS: the Vite proxy puts the app and `/api` on one origin.

## Formats

- Times: 24-hour `HH:MM`. Timestamps: ISO 8601 UTC.
- Days: letters from `MTWRFSU` (R = Thursday).
- JSON fields: `snake_case` everywhere, front end included. Missing values are `null`, not omitted.

## Data model

Eleven contract tables, plus `doc_chunks` (RAG), `student_requirements` and `refresh_runs` (migration `0002_data_retrieval`, Nov 17), and `calendar_events`, `student_preferences` and `student_settings` (migration `0003_student_planning`, Nov 18). Each section's meeting time lives on the section row, because one export row is one section with one time. Labs (`002L`) are their own sections.

| Table | Fields | Notes |
| --- | --- | --- |
| `terms` | id, code, name, is_current_registration | e.g. Spring 2027. `is_current_registration` = the term the latest schedule export covers |
| `courses` | id, code, title, department, credits, description, other_requirements | `code` like `CSCI 3103`; description from SAU catalog. `department` and `credits` come from the sections export, so they are `null` for courses not offered this term |
| `course_prereqs` | course_code, requires_code, option_group | One row per prereq. Rows sharing an `option_group` are alternatives (any one counts). Empty = no prereqs |
| `sections` | id, course_id, term_id, section_number, instructor, location, building, room, days, start_time, end_time, division, enrolled, capacity, active | Blank days/times = online or TBA. Blank instructor = "Staff". `start_time`/`end_time` are Postgres `time` columns; the API formats them as `HH:MM`. One row per (course, term, section number). A section missing from a newer export is set `active=false`, **never deleted**, because saved schedules point at it |
| `degree_plans` | id, name, catalog_year, total_hours, source_url, scraped_at | e.g. "Computer Science, BS", "2026-2027". `catalog_year` is text. `source_url`/`scraped_at` set by the degree map scraper |
| `requirement_groups` | id, degree_plan_id, parent_id, name, rule, hours_required, sort_order, note | Tree of requirements. `note` = rules that are not a course list ("may only include one course in Art"), shown, not enforced |
| `requirement_courses` | group_id, course_code | Courses that count toward a group |
| `students` | id, name, email, password, degree_plan_id, classification, major, catalog_year, has_hold, total_hours_earned, total_hours_needed, audit_refreshed_at | Demo accounts only. Plain demo password is fine for semester 1. The audit fields come from mySAU connect; `has_hold` is a yes/no only. Connect also sets `name` to the audit's "First Last" (Nov 18) |
| `completed_courses` | id, student_id, course_code, status, grade, credits, term, source, requirement_name | `status` = `completed` or `in_progress`. `source` = `audit`, `self_reported` or `manual` (default). Key is `id`: one course can appear on several audit lines (two requirements, a retake, or also self-reported). `requirement_name` is null for nonapplied coursework |
| `student_requirements` | id, student_id, name, parent_name, status, rule, hours_earned, hours_required, course_options, note, sort_order | A connected student's audit blocks. `status` = `met`, `not_met`, `in_progress`; `rule` = `all` or `choose_hours`; `course_options` (text[]) = the "Select N hours from…" list or the required courses |
| `refresh_runs` | id, kind, status, started_at, finished_at, rows_changed, error, student_id | One row per scrape or connect. `kind` = `course_info`, `degree_maps`, `sections`, `audit`; `status` = `running`, `ok`, `failed`. `error` is a short message of our own, never page content. `student_id` null for public runs |
| `schedules` | id, student_id, term_id, name, source, created_at | source = `manual` or `ai` |
| `schedule_sections` | schedule_id, section_id | |
| `calendar_events` | id, student_id, title, day, start_time, end_time, location, category, recurrence, priority, fixed, created_at, updated_at | The student's own commitments. `day` = one letter of `MTWRF`; times are Postgres `time` (start before end). `category` = `work`, `personal_study`, `extracurricular`; `recurrence` = `none`, `weekly`; `priority` = `low`, `normal`, `high`. `fixed` events block courses (checker conflict), others only warn. Events have a weekday, not a date: the checker treats every event as weekly. Classes aren't events: the calendar shows a saved schedule's sections |
| `student_preferences` | student_id (key), preferred_time, preferred_days, min_credits, max_credits, delivery, flexibility, updated_at | One row per student; no row = the defaults (`none`, no days, 12–18 credits, both deliveries, `balanced`). `preferred_time` = `morning`, `midday`, `afternoon`, `evening`, `none`; `preferred_days` = letters from `MTWRF`; `delivery` (text[]) is `in_person` and/or `online`; `flexibility` = `flexible`, `balanced`, `strict`. The front end's travel distance and minimum rating are mock and not stored |
| `student_settings` | student_id (key), email_notifications, push_notifications, advisor_updates, schedule_alerts, appearance, high_contrast, larger_text, reduce_motion, profile_visibility, photo, updated_at | One row per student; no row = the defaults (notifications on, `light`, accessibility off, `advisors`). `appearance` = `light`, `dark`, `system`; `profile_visibility` = `private`, `advisors`, `community`; `photo` = an image data URL (png, jpeg, gif or webp, at most ~1 MB; SVG refused) |

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
   - **Returning Student (`returning.student@demo.flowsaic.test`, user 4):** no plan, no fake courses. Fills their own record with Connect mySAU (the real schedule + their own audit, and their first and last name in place of "Returning Student") and **keeps it** across restarts, sign-outs and seed runs, like a student coming back. It then holds a **real audit and a real name**: run `seed_demo.py --clear-returning` before a database dump is shared (it also puts the placeholder name back). Seed runs reset only the password, never the connected name. The seed turns the old user 4 row (`new.student@demo.flowsaic.test`) into this one, keeping its data.
   - **New Student (`new.user@demo.flowsaic.test`, user 5):** a first-time student every time. Same Connect mySAU (which renames them to their real first and last name), but **emptied** (audit courses and requirements, audit fields, saved schedules, calendar events, preferences, settings and photo, and the name goes back to "New Student") when the backend starts, when they sign in, when they sign out and on every seed run (`demo_seed.clear_new_student`). The shared course schedule is never cleared. A connect still running when user 5 signs out can save afterwards; their next sign-in clears it.
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
- **Startup never waits:** the check runs in a background thread. Runs cut off by a restart are marked `failed` at the next startup, every startup, even with `PUBLIC_REFRESH_ON_STARTUP` off (Nov 18; a cut-off audit used to stay `running`). Partial CLI runs (`--only`, `--limit`) are not recorded, so they never look like a fresh refresh.

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

Endpoints for this (added by prompt 2; counted among the thirty-one under API endpoints; `/data/*` and `/connect/mysau` have no session check yet):

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/data/refresh/public` | | 202 `{ runs: [{ id, kind }] }` (degree_maps, then course_info, in the background); 409 `refresh_already_running` |
| GET | `/data/refresh/{id}` | | The `refresh_runs` row; 404 `refresh_run_not_found` |
| POST | `/connect/mysau` | `{ student_id, fetch: ["sections", "audit"] }` | 202 `{ runs: [{ id, kind }] }`; 404 `student_not_found`; 409 `connect_already_running` |
| POST | `/me/connect-mysau` | `{ fetch }` (optional, default both) | Same as above for the **signed-in** student; 401 `not_authenticated`. Used by the prototype home page |
| GET | `/me/audit` | | `{ refreshed_at, requirements: [...] }`: the student's `student_requirements` (their mySAU audit blocks). Empty list if never connected |

### mySAU connect

- A **headed** Chromium window opens on the machine running the backend (fine for the demo laptop; a hosting problem for semester 2). The student signs in themselves (Microsoft + Duo); the script waits up to 5 minutes and never types into the sign-in. "Signed in" = back on my.saumag.edu with the Login button gone.
- The audit attaches to an **existing** Flowsaic student (`student_id`). It never creates a student and never changes email or password. It sets the student's name to the audit's first and last name ("Fakerson, Testy Q." → "Testy Fakerson"; unreadable names are skipped and the old name stays). It replaces only that student's `source='audit'` course rows and their `student_requirements`, in one transaction.
- Selectors are role/text selectors from a codegen recording (Nov 17), not CSS positions. Re-record with `uv run playwright codegen https://my.saumag.edu/ICS/` if mySAU changes (turn recording off while signing in).

**Privacy rules (non-negotiable):**
- Never store, log or print a mySAU password, cookie, token or Playwright `storage_state`. Fresh browser context every run, closed in `finally`. No persistent profile. Downloads are refused by the context.
- Playwright tracing, video and screenshots stay **off** for mySAU pages. A test fails if the connect code ever calls them.
- Never log page HTML or audit text. Errors in `refresh_runs` are our own step code (with the sub-step), the error type and a fixed hint of ours (`audit_export:academics_link failed (Error: more_than_one_match)`). When no hint fits a Playwright error, the start of Playwright's own wording is kept, cut before any quote, tag, bracket or URL so no page text gets in (`Locator.click: Element is outside of the viewport`).
- Each export (course schedule, audit) runs on its own: one failing doesn't lose the other. Every export starts from the mySAU home page, and "signed in" means the same signed-in page for 3 checks in a row, because mySAU keeps redirecting for a moment after Microsoft sign-in.
- The audit PDF and the schedule CSV are captured from the network response **in memory only**; the browser is shown a "received" page instead of a download. Never write the audit PDF to disk and never commit any PDF (`*.pdf` and `data/private/` are gitignored).
- From the audit, the header is discarded except the student's **first and last name** (Nov 18; no middle name or initial): ID number, address, phones, advisor, GPA are never read. Later lines that repeat the name (the page footer) are still dropped, so the name never ends up in requirement or course text. Holds become only `has_hold` (a hold's name can reveal a balance owed). Kept: major, catalog year, classification, course lines (code, grade, credits, term, status), requirement statuses (name, met / not met / in progress, hours) and total hours earned/needed.
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
| A section meets during a **fixed** calendar event (Nov 18) | Conflict | `commitment_overlap` |
| A section meets during a flexible calendar event (Nov 18) | Warning | `commitment_overlap_flexible` |

Overlap: same day and `start_a < end_b and start_b < end_a`. Online/TBA sections never cause a time conflict. Lecture/lab pairing is not enforced in semester 1.

**Built Nov 17 (`app/checker.py`, `POST /schedules/check`).** Details:
- `missing_prereq`: every prereq group needs one option passed (not F/W) or in progress. A course in the same schedule doesn't count. Message: "MGMT 2003 needs ENGL 1113 and ENGL 1123 (passed or in progress)".
- `already_completed`: passed courses only (in progress isn't completed).
- `not_on_plan`: not listed in the student's plan and not matching one of its subject/level electives (for a connected student: not in any audit requirement's course options). Says "(it would count as a general elective)" when the plan has unrestricted electives. No warning for a student with no plan yet.
- `over_credit_limit`: each course counted once; exactly 18 is fine.
- Errors: 404 `section_not_found` (unknown or inactive section), 422 `section_not_in_term`. Duplicate IDs in the request are dropped.
- **Commitments (Nov 18):** the checker loads the student's `calendar_events` itself, so every place it runs applies them: `/schedules/check`, saving, `GET /schedules/{id}`, AI suggest and Flow's tools and proposals. Same overlap rule as `time_overlap`; online/TBA sections never overlap an event. Messages name the event's category, never its title ("MATH 3043-001 meets during your work commitment (W 10:00-11:00)"), because titles are the student's own words and checker messages also go to Gemini. Commitment items carry `event_ids` too.

**Solver (`app/solver.py`, built Nov 17; Nov 18: `midday` (starts 11:00–13:59), soft `preferred_days`, soft `flexible_blocks`).** `find_schedules(must, optional, constraints)` returns up to 5 section combinations (one section per course, no time overlaps), best first, plus the must courses that can't be placed and why. Optional courses are added best first until the credits reach the target. Hard constraints: unavailable blocks, earliest start, latest end, days off, instructors to avoid, open seats only, no online, online only (Nov 18). Soft (ranking): preferred time of day, preferred days, lunch, preferred instructors, flexible calendar events, fewer days on campus, avoiding full sections. When Flow calls it, the student's **fixed** events are always added as unavailable blocks (Flow can't forget them) and flexible ones as soft blocks. A tool for Flow; every result still goes through the checker.

Each item: `{ "code": "time_overlap", "section_ids": ["...", "..."], "message": "CSCI 3103 and MATH 2753 overlap on MW 10:00", "event_ids": [] }`. The front end shows `message` as is. `event_ids` lists the calendar events involved (commitment codes only; `[]` otherwise).

## Flow, the AI advisor (decided Nov 17)

Flow is Flowsaic's AI advisor (Gemini behind it), on Andy's AI Advisor page. It's a conversation, not a form: it explains degree progress, finds courses and electives that fit what the student wants, builds and adjusts schedules around constraints, and asks for what it needs ("how many credits?", "any times you can't do?"). Endpoint: `POST /ai/advisor` `{ message, history }` → `{ reply, memory, proposals, suggestions }` (each proposal is a checked schedule; `suggestions` = up to 3 quick replies). **Built Nov 17** (`app/advisor.py`, `app/routers/ai.py`).

- **What Flow knows:** the student's record from SQL (their **first name**, classification, major, catalog year, hours, completed and in-progress courses with F/W not counting, what's still needed from the audit or the degree map, and elective candidates found by code: subject, level, offered this term, prereqs met), the student's calendar commitments (category, day and time only, never the title or location; fixed ones are hard limits) and saved scheduling preferences (defaults unless the student says otherwise), plus the last 20 messages (sent by the front end).
- **Tools Flow calls (Gemini function calling), all scoped to the signed-in student:** `get_my_progress`, `find_courses` (RAG over courses the student can take), `get_sections`, `check_schedule` (the checker), `find_schedules` (a solver that returns section combinations meeting constraints), `propose_schedule` (a checked schedule card).
- **Code does the exact work** (eligibility, counting, time conflicts, combinations); Flow chooses, explains and talks. That's what keeps a fast model reliable.
- Every schedule Flow shows has been through the checker; conflicts are shown, never hidden. **Flow never saves**: the schedule card has a Save button the student clicks.
- **A card every time (Nov 18):** Flow is told to call `propose_schedule` every time it presents or changes a schedule, however late in the conversation, and never to describe one in text only (a text-only schedule had no Save / Open in Create Schedule button). Backstop: a reply that names 2+ course codes but has no card gets a "Show this as a schedule" quick reply. Tested live Nov 18: 5 of 5 schedule turns in a 6-turn chat made a card.
- **Quick replies (Nov 18):** Flow ends every reply with `Quick replies: a | b | c` (2–3 short replies in the student's voice: answers to its question, or likely changes). The backend takes that line out of `reply` and `memory` and returns the items in `suggestions` (at most 3, 60 characters each). No extra Gemini call. The front end shows them as buttons; one click sends it as the next message.
- **Personal:** Flow greets and addresses the student by first name. Since Nov 18 (Victor's decision) the **first name is in the record sent to Gemini**; the last name, email and ID never are. Users 4 and 5 have no name until they connect mySAU, so the record says the name isn't known and Flow uses none. A `{first_name}` Flow writes anyway is still filled in by the backend.
- **How the loop works:** up to 10 Gemini calls per message (tools disabled on the last); two steps before the end Flow is told to propose and wrap up; an empty answer gets one plain retry. Tool results go back with role `user` (the API rejects `tool`). Sections are referred to by labels like `CSCI 4203-001`, never IDs.
- **Speed (Nov 18):** nearly all the time is Gemini round trips (3–7 s each; our own code is ~0.2 s). Flow is told `find_schedules` options are already checked (no `check_schedule` or `get_sections` on them), to call tools together, and to show an option with `propose_schedule(option=N)` instead of listing sections. When a step only proposes clean schedules (no conflicts, and no warnings unless it was a `find_schedules` option) and Flow wrote its reply in the same response, the loop stops without another call. Measured Nov 18 on `gemini-3.8-flash` (Alex): a specific request ("no Fridays, ~12 credits") 16–19 s in 3 calls; a vague one ("a balanced schedule") 21–26 s in 4–6 calls (it was ~26 s, once 40 s). Flow rarely writes its reply alongside the card yet, so the early stop seldom fires.
- **Front end:** keep the conversation and send it back as `history` (last 20). For Flow's turns send the reply's `memory`, not `reply`: `memory` also lists the schedules shown. Each `proposals[]` item is a checked schedule (`term_id`, `section_ids`, sections, credits, conflicts, warnings); its Save button calls `POST /schedules` with `source: "ai"` (blocked while it has conflicts).
- Errors: 503 `gemini_model_not_set`, 502 `ai_unavailable`.
- **Guardrails (tested Nov 17 with messy, real-student prompts):** Flow looks a course up before saying it is or isn't offered (`get_course` also returns related courses, e.g. the whole Senior Project sequence, each with offered/blocked status); says it doesn't know anything outside Flowsaic's data (no made-up restaurants, dates or policies); asks one question when a new constraint is vague ("I have a job") instead of guessing; says when a swapped-out course is still required; never claims to register or save.

## AI suggest (Gemini, the Create Schedule form)

The Create Schedule page's **Auto-generate**. **Rebuilt Nov 18** (`app/suggest.py`, `POST /ai/suggest`): **code builds the schedule and Gemini only explains it**, ~2.5–3.5 s instead of ~20 s (it used to run Flow's whole tool loop). The request and response didn't change. Only the current registration term is supported (`term_id` for another term → 422 `term_not_supported`).

1. Student hits Auto-generate (with the form's preferences, merged with their saved ones).
2. **Courses:** the student's can-take list (`app/progress.py`: offered, not taken, prereqs met), required first, then choice, then electives, at most one course per choice group or elective line. Form `notes` move the courses whose description matches them up the list (one RAG search, ~0.35 s; none without notes).
3. **Sections:** the solver picks the best combination. Fixed calendar events and `unavailable` times are hard limits, and so is delivery (`in_person` only = no online sections; `online` only = only online/TBA sections). Preferred time and days, lunch, instructors and flexible events only rank. Credits: `target_credits`, else the saved `min`/`max`, else 12–15. If the minimum can't be reached, the most credits that fit are taken.
4. **The checker** runs on it, as on every schedule.
5. **One Gemini call, no tools,** writes the 2–3 sentence `explanation` (low thinking: 9.1 s → 2.9 s, measured Nov 18). Gemini never picks or changes sections here. Without a Gemini key or model, or if the call fails, a plain sentence written by code is used, so Auto-generate works offline too.
6. Nothing fits → empty `sections` and an `explanation` saying why.

Trade-off: free-text `notes` only re-rank courses now (by meaning); a rule typed into notes ("nothing before 10") isn't understood. Chat with Flow still is.

Preferences are all optional: `term_id`, `target_credits`, `min_credits`, `max_credits`, `unavailable` (list of `{days, start, end}`), `preferred_time` (`morning` / `midday` / `afternoon` / `evening` / `none` / blank), `preferred_days` (letters `MTWRF`), `delivery` (`in_person` and/or `online`), `lunch`, `preferred_instructors`, `avoid_instructors`, `notes`. **The student's saved preferences (`/me/preferences`) fill every field the request leaves out** (Nov 18); the request body wins. Saved flexibility `strict` / `flexible` is passed along as "treat these as firm" / "light wishes". Fixed calendar events are always kept free. Gemini treats preferences as wishes and checker rules as hard limits.

- Model name and key come from `.env` (`GEMINI_MODEL`, `GEMINI_API_KEY`), so switching models is a one-line change.
- **Set a spending cap in the Google account before the first call.**
- Send the LLM course data, preferences and the student's **first name** only (first name since Nov 18). Never last names, emails or IDs; use the student's degree plan and course codes.
- Gemini's explanation is plain text; it can't add or change sections (no tools, and the sections come from code).

## RAG (part of the system)

RAG is a core part of Flowsaic, not a stretch goal (decided Nov 16; the contract's RAG section matches). It gives Gemini the course text SQL rows can't: descriptions and catalog/policy wording.

Decided:
- **One Postgres database with pgvector.** No separate vector DB.
- **RAG is for unstructured text only** (course descriptions, catalog/policy text). Structured data (sections, times, prereqs, degree plans, completed courses) always comes from SQL, never from vector search.
- RAG ranks, it never decides: in AI suggest it moves can-take courses matching the form's notes up the list (Nov 18), and Flow uses it in `find_courses`. It never replaces the eligible list, the solver or the checker.
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
- **Query:** for AI suggest, the form's `notes` (empty `notes` = no search); for Flow, its own `find_courses` query.
- **Ranking:** cosine distance, HNSW index (`vector_cosine_ops`), top 8.
- **Embed script** sends descriptions in batches to stay under rate limits. Embedding all of them costs a few cents.

## API endpoints

Thirty-one endpoints (contract v2 plus Nov 18): the table below (the sixteen of v2, `POST /ai/advisor`, and the nine added Nov 18: `GET /search` and the eight `/me/events`, `/me/preferences`, `/me/settings` routes), and the five data/connect endpoints listed under Data sources (`/me/audit`, `/me/connect-mysau`, `/connect/mysau`, `/data/refresh/public`, `/data/refresh/{id}`). Everything except login, `/data/*` and `/connect/mysau` needs the session cookie and acts on the logged-in student.

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{ email, password }` | Student; sets session cookie |
| POST | `/auth/logout` | | 204 |
| GET | `/me` | | Student name, plan, classification |
| GET | `/me/progress` | | `{ source, plan, term, hours, requirements (tree: status met/in_progress/not_met/not_tracked, hours, courses, electives), can_take, blocked, open_electives }` |
| GET | `/me/completed-courses` | | List of `{ course_code, status }` |
| PUT | `/me/completed-courses` | `{ courses: [{ course_code, status }] }` | Replaces the whole list |
| GET | `/terms` | | Terms (`id, code, name, is_current_registration`), current registration term first |
| GET | `/courses` | Query: `term_id` (required), `search`, `department`, `on_my_plan`, `eligible_only`, `level`, `delivery`, `open_only`, `credits`, `days`, `limit` (default 50, max 100), `offset` | `{ total, courses, departments }` (see Catalog below) |
| GET | `/courses/{id}` | Query: `term_id` (optional, default the current registration term) | One course with prereq groups, flags and every section in the term (inactive ones too) |
| GET | `/search` | Query: `q` (2–100 characters), `limit` (default 10, max 20) | `{ query, results: [{ course_id, code, title, snippet, match_type, offered }] }` |
| GET / POST | `/me/events` | none / an event | My calendar events / the new event (201) |
| PUT / DELETE | `/me/events/{id}` | an event / none | The updated event / 204. Another student's event is 404 `event_not_found` |
| GET / PUT | `/me/preferences` | none / any preference fields | My scheduling preferences (defaults if never saved) |
| GET / PUT | `/me/settings` | none / any settings fields | My settings and photo (defaults if never saved) |
| POST | `/schedules/check` | `{ term_id, section_ids }` | `{ conflicts, warnings }` |
| GET | `/schedules` | | My saved schedules |
| POST | `/schedules` | `{ name, term_id, section_ids, source }` | Saved schedule, or 422 with conflicts |
| GET | `/schedules/{id}` | | Schedule with full section details for the calendar |
| PUT / DELETE | `/schedules/{id}` | Same body as POST / none | Updated schedule / 204 |
| POST | `/ai/suggest` | Preferences | `{ section_ids, sections, explanation, warnings, conflicts }` |
| POST | `/ai/advisor` | `{ message, history }` | `{ reply, memory, proposals, suggestions }` (Flow; each proposal is a checked schedule; `suggestions` = up to 3 quick replies, Nov 18) |

**Catalog (built Nov 18, `app/routers/catalog.py`).** `/courses` lists courses with an active section in the term, with those sections. `search` matches code (a typed code like `csci4203` works), title or description. Every course has the signed-in student's flags, computed from the same tree as `/me/progress` (`progress.course_flags`): `eligibility` (`eligible`, `missing_prereq`, `completed`, `in_progress`; F and W aren't completed), `missing_prereqs`, `on_my_plan`, `requirement_names` (the requirements listing it, or the elective line it would fill), plus `level` (from the number: 3000), `prereqs` (option groups), `offered` and `seats_open`. Each section has `seats_open`, `active`, `HH:MM` times, day letters and `delivery`: `online` when it has no days/times or its campus says online, otherwise `in_person` (the export has no hybrid flag). `level`, `delivery` (has such a section), `open_only`, `credits` and `days` (has a section meeting exactly those days) are filters too, applied before paging so `total` stays right. `departments` lists every department offered in the term. Errors: 404 `term_not_found`, 404 `course_not_found`.

**Header search (built Nov 18, `GET /search`).** Code/title matches first (`match_type` `code` or `title`), then the courses whose description is closest in meaning (`description`, the same RAG search Flow uses, now in `app/course_search.py`). `offered` = has an active section in the current registration term. Without a Gemini key, or if the embedding call fails, it returns the text matches only. Each new query costs one embedding request; repeats are cached until the server restarts.

**Events, preferences, settings (built Nov 18, `app/routers/planning.py`).** Session required; every row is the signed-in student's own. An event is `{ title (1–80), day (M T W R F), start_time, end_time (HH:MM, end after start), location, category, recurrence, priority, fixed }`; at most 60 per student (422 `too_many_events`). `PUT /me/preferences` and `PUT /me/settings` change only the fields sent (a field left out keeps its value; for settings, `"photo": null` removes the photo). Preferences with min over max credits are 422 `invalid_credit_range`. A missing row returns the defaults with `updated_at: null`, never 404. The photo must be a base64 png/jpeg/gif/webp data URL of at most ~1 MB.

**Built (Nov 17):** `POST /auth/login`, `POST /auth/logout`, `GET /me`, `GET /me/progress`, `GET /me/completed-courses` (also returns title, grade, credits, term, source, requirement_name), `POST /schedules/check`, `GET/POST /schedules`, `GET/PUT/DELETE /schedules/{id}`, `POST /ai/advisor`, `POST /ai/suggest`.

**Saving schedules (built Nov 17):** `POST` and `PUT /schedules` run the checker first; conflicts block saving with 422 `{ "error": "schedule_has_conflicts", "conflicts": [...] }`, warnings don't. Another student's schedule is 404 `schedule_not_found`. `GET /schedules/{id}` returns the sections (with `active`; a section dropped from a later export stays, marked inactive) plus a fresh check.

**Prototype login (Nov 17, temporary):** `email` also accepts the usernames `1`–`5` (1 Alex, 2 Jordan, 3 Sam, 4 Returning Student, 5 New Student; see Data loading) and **the password is not checked**. Sessions are a random token in an HttpOnly cookie, kept in the server's memory (a restart signs everyone out). Errors: 401 `invalid_credentials`, 401 `not_authenticated`. Real passwords and server-side sessions are semester 2.

**Prototype pages (Nov 17, now a developer tool):** the React app (Front end, below) is the product. The backend still serves a sign-in page at `/` (`backend/app/static/login.html`). Signing in opens the tabbed test page at `/dev` (`dev.html`): **My profile** (with Saved schedules), **AI Advisor** (Flow, with schedule cards and Save; it replaced the old Chat tab, whose `/dev/chat` endpoint is no longer used by the page), **Schedule lab** (try the checker and the solver; its helper endpoints `GET /dev/lab/sections` and `POST /dev/lab/solve` are test-page only, not contract), Search, Browse, Database. `/dev` sends you back to `/` when you're not signed in; `/home` redirects to `/dev`. This lets the flow be tested before the React front end is wired up. My profile only calls the endpoints above: users 1–3 show their demo record; users 4 (returning, keeps its data) and 5 (new, emptied at every startup, sign-in and sign-out) have a **Connect mySAU** button. Demo students don't get the button, so a real audit never mixes into a fake student.

The dashboard uses `/me`, `/me/progress`, `/me/completed-courses`, `/me/events` and `/schedules`; there's no separate dashboard endpoint. Exact response fields are defined in the backend's `/docs` (FastAPI generates them). Andy reads `/docs`, not this table, for field names. Front end builds against mock JSON in that shape until the endpoint is live.

## Front end (wired Nov 18)

React 19 + TypeScript + Vite in `/frontend`, no router or data libraries. Run: `npm install` once, then `npm run dev` from `frontend/` (or just `start.cmd`), and open **http://localhost:8443/**. `npm run build` type-checks (`tsc --noEmit`) and builds; it must pass.

- **Proxy, not CORS:** the app always calls `/api/...`. Vite's dev server forwards `/api/*` to `http://127.0.0.1:8000` (or `BACKEND_URL`) with `/api` stripped, so the session cookie stays on the app's own origin. CORS (`FRONTEND_ORIGINS`) is only for calling the backend directly. Vite binds to `localhost` only (the Figma config used `0.0.0.0`, which put the app and, through the proxy, the backend on the Wi-Fi).
- **Code layout:** `src/api/client.ts` (every call, `credentials: 'include'`), `src/api/types.ts` (backend shapes, snake_case, mirror `/docs`), `src/api/adapters.ts` (backend ↔ UI shapes: day letters ↔ the UI's day keys and index, `HH:MM` ↔ decimal hours and "2:10 PM"), `src/api/errors.ts` (`{ error: code }` → friendly toast text), `src/pages/*.tsx`, `src/components/`, `src/types.ts`, `src/mock.ts`.
- **Errors:** every `{ error }` shows as the existing toast with a friendly message. Any 401 sends the user back to the sign-in screen.
- **Wired:** sign-in (usernames 1–5 or an email, any password; `/me` on load, `/auth/logout`), header and profile (`/me`), the real date and the current registration term (`/terms`), Dashboard and Degree Progress (`/me/progress`, `/me/completed-courses`; "Add to plan" adds the course to the Create Schedule draft), Course Catalog (`/courses`, filters, Load more, `/courses/{id}`), header search (`/search`, on Enter or 400 ms after typing, from 2 characters), Create Schedule (course list from `/courses`; **every change runs `/schedules/check`**, and its conflicts and warnings are what the page shows, commitment codes included; no client-side conflict logic; Auto-generate = `/ai/suggest`; Save draft = `POST`/`PUT /schedules` with a name, 422 `schedule_has_conflicts` handled; a picker for this term's saved schedules; Delete; online/TBA sections in their own list, not on the grid), My Calendar (`/me/events` CRUD plus the sections of a saved schedule picked on the page, read-only; the draft shows as "Proposed"), Scheduling Preferences (`/me/preferences`), Settings and the profile photo (`/me/settings`; appearance and accessibility apply on click, Discard reverts), Flow on the AI Advisor page and the dashboard's Ask Flow (`/ai/advisor`; `history` sends Flow's turns as `memory`; users 4 and 5 are greeted without a name until Connect mySAU brings their real one; schedule cards with Save (`source: "ai"`) and Open in Create Schedule; a **Latest schedule bar** pinned above the message box with the newest card's Save and Open in Create Schedule, so they never scroll away; Flow's `suggestions` as quick-reply buttons under its last reply (generic ones if it gave none); the chat lives in memory only), Connect mySAU on My Profile for students without a demo plan (users 4 and 5: `/me/connect-mysau`, then polling `/data/refresh/{id}`).
- **Still mock (`src/mock.ts`, don't wire before semester 2, don't delete):** the Semester Planner (several terms; its sample courses aren't SAU's, and "Send to Create Schedule" just opens the real builder), the Advisor Dashboard and the submit-for-approval status, professor ratings (no rating data exists; real courses show "No reviews yet" and "Rate this course" keeps a rating on the page only, so no made-up ratings ever sit next to a real instructor), the notifications bell, degree map checkoff (`PUT /me/completed-courses` isn't built), and the travel-distance and minimum-rating preference fields (this device only). Nothing wired reads from `mock.ts`.
- **This device only (localStorage):** the theme before sign-in, the unsaved Create Schedule draft (per student), the mock fields above. Everything else lives in the backend.

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
- Backend (Nov 17): repo now at `Documents\GitHub\Flowsaic`. Working: `GET /health`, `/dev`, settings, all models, migrations `0001` + `0002_data_retrieval`, the loaders, embeddings, `search.py`, the public scrapers (course info, degree maps with gen ed), `POST /data/refresh/public` + `GET /data/refresh/{id}` + background refresh on startup, and mySAU connect (`POST /connect/mysau`, CLI) with the audit parser, both tested live once, the full degree map scrape, `seed_demo.py` (3 demo students + users 4 and 5), prototype login (`/auth/login`, `/auth/logout`, `/me`, `/me/completed-courses`, `/me/audit`, `/me/connect-mysau`) and the sign-in page + the My profile tab on `/dev`. `/me/progress` with the progress tree and "You can take" on My profile. The schedule checker (`POST /schedules/check`) and the solver, with the Schedule lab tab. Flow (`/ai/advisor`, live-tested with Alex and Sam), AI suggest, and saving schedules (`/schedules`), with the AI Advisor tab and Saved schedules. 194 tests pass. Nov 18: CORS (`FRONTEND_ORIGINS`), the catalog endpoints (`/terms`, `/courses`, `/courses/{id}`) with per-student flags, `GET /search`, migration `0003_student_planning` and `/me/events`, `/me/preferences`, `/me/settings`, the commitment checks (`commitment_overlap`, `commitment_overlap_flexible`) everywhere the checker runs, Flow and suggest told the student's commitments and saved preferences, `setup.cmd`/`start.cmd` running the front end too. Connect mySAU keeps the first and last name, and Flow is given the first name. Auto-generate rebuilt in code (~3 s, `app/suggest.py`) and Flow's schedule replies trimmed (`propose_schedule(option=N)`). Flow makes a card for every schedule change and returns quick replies (`suggestions`); the AI Advisor page pins the latest schedule. Teammate setup tested end to end Nov 18 on a fresh copy (path with a space, no installs, an empty database): found and fixed the course-info step loading nothing into a fresh database; `setup.cmd` then reached "All set!" and `start.cmd` served sign-in, the catalog, progress, search and Auto-generate. 371 tests pass. Not built yet: `PUT /me/completed-courses`, `load_degree_plans.py`, the Course Search fallback.
- Course data: `/data/course_info.csv` done (1,878 courses, Nov 16). `data/raw/degree_maps/` holds the saved program pages. Not committed yet.
- Database (Victor, Nov 17): Postgres 17 + pgvector 0.8.7 in Docker on port 5433. Loaded: 1 term (Spring 2027, current registration), 1,965 courses, 1,025 prereq rows, 1,353 sections (1,343 active), 1,868 embedded chunks, 139 degree plans (every undergraduate program and minor on the 2026–27 catalog; 1,726 requirement groups), 3 demo students (`seed_demo.py`). The live mySAU test student was deleted Nov 17, so no real audit is in the database. Empty: schedules, calendar events, preferences, settings. Migration `0003` applied Nov 18.
- Front end (Nov 18, wired by Victor with Andy's OK): the React app runs on the real backend end to end (see Front end). `npm run build` passes. Clicked through the demo path as users 1 and 5 on Nov 18 (sign-in, dashboard, degree progress, catalog, header search, Create Schedule with the live checker and commitment conflicts, saving, calendar, Flow, Auto-generate, preferences, settings, session expiry). Connect mySAU from the React page not yet tried live (it needs a real sign-in). Still mock: see the Front end section.

## Decisions log

- **Nov 16:** the earlier database/RAG scripts (`documents`/`chunks` tables, keyword search, `ingest.py`, `api.py`, `load_courses.py`) are **replaced** by the contract schema. Don't use or copy them. Victor builds the new schema and migrations.
- **Nov 16:** schema built. Additions beyond the contract's field lists, which the contract doc still needs: `courses.other_requirements` (nullable text), `sections.start_time`/`end_time` as `time` columns, `degree_plans.catalog_year` as text, and the `doc_chunks` shape in the RAG section.
- **Nov 16:** sections importer keeps one meeting time per section and skips canceled sections (see Data loading).
- **Nov 16:** embedding text formats for `gemini-embedding-2` are fixed (see RAG). Changing them means re-embedding every row.
- **Nov 16:** local database runs on host port 5433, bound to this laptop only (`127.0.0.1` and `::1`). Its dev-only password is in `docker-compose.yml`; it protects fake data in a local container and must never be reused.
- **Nov 17: automated data retrieval.** Flowsaic fetches its own data: public scrapers for course descriptions and degree maps, and a student-run mySAU connect for the course schedule and the degree audit (see Data sources). Migration `0002_data_retrieval` adds the columns and the `student_requirements` and `refresh_runs` tables. `completed_courses` now has an `id` key because one course can appear on several audit lines.
- **Nov 17: Playwright connect, no stored credentials.** The student signs in themselves in a visible browser; the script never sees or stores a password, cookie, token or session, and files are captured in memory. This is the one place Flowsaic works behind a login, and only with the student at the keyboard.
- **Nov 17: audit header discarded.** Name, ID, address, phones, advisor and GPA are never stored; holds are a yes/no only. (Changed Nov 18 for the name: see below.) For a connected student the audit is their degree plan; public degree maps are the fallback.
- **Nov 17: catalog bot protection is respected.** catalog.saumag.edu's list and program pages are behind an AWS WAF challenge; we don't get around it. Course text is reused from the Nov 16 scrape and re-crawled (120 s/page, robots.txt) only for a new catalog year. Degree maps come from www.saumag.edu's open program pages instead.

- **Nov 18: student planning data.** Calendar events, scheduling preferences and settings live in the backend (migration `0003`). Fixed events are checker conflicts (`commitment_overlap`), flexible ones warnings (`commitment_overlap_flexible`). Events are weekly blocks (they have a weekday, not a date). Gemini sees an event's category, day and time only, never its title or location.
- **Nov 18: the React front end is the product; the backend checker is the only judge.** The front end calls the backend through Vite's `/api` proxy (one origin, cookie included) and has no conflict logic of its own. The backend's `/` and `/dev` pages stay as developer tools. Saved preferences are the default for AI suggest and Flow; the request wins.
- **Nov 18: the student's name (Victor's decision).** Connect mySAU keeps the audit's first and last name (no middle name or initial) as `students.name`, so users 4 and 5 show their real name instead of a placeholder. Flow's record sent to Gemini includes the **first name** so it can personalize; the last name, email and ID still never go to Gemini. Emptying users 4 and 5 puts the placeholder names back. This reverses the Nov 17 "name never stored" rule and the "never send names to the LLM" rule for the first name only.
- **Nov 18: faster schedules.** Measured first: the time was Gemini round trips, not our code. Auto-generate is now built by code (courses from can-take, the solver, the checker) with one low-thinking Gemini call for the explanation only (~20 s → ~3 s). Flow keeps its tools but skips redundant ones and can propose a `find_schedules` option by number. Not done yet (needs a decision): low thinking for chat calls, and streaming progress to the page (a contract change).
- **Nov 18: no fake ratings.** Professor ratings stay mock, but real courses start with no reviews instead of invented numbers next to real SAU instructors.

## Open questions (don't build around these yet)

- **Sections with more than one meeting time.** 86 sections have 2–3 meeting times, but `sections` stores one, so the conflict checker misses 87 real meeting times. Storing them needs a meetings table, which is a contract change.
- **Mixed AND/OR prereqs.** 15 courses are encoded wrongly in `course_info.csv` (see Data loading). Decide whether to fix them by hand or blank them like the other `needs_review` rows.
- **High-school concurrent sections** (39 rows, `concurrent = Yes`) are loaded like any other section. Decide whether the catalog should hide them.
- **Hand fixes to `course_info.csv`** are overwritten whenever `scrape_course_info.py` rebuilds it. Option: a small `data/course_info_overrides.csv` applied after every rebuild.
- **Failing grades on the audit** (F, W) are stored as `completed` with their `grade`. Anything that counts completed courses (checker, progress) must look at `grade` too. Demo student Sam Okafor has such a row (PSYC 3183, F, retaken in Fall 2026).
- **Course titles from the audit** aren't stored (no column); the title comes from `courses` by code. Transfer lines are stored as the SAU course they count as (e.g. `ENGL1013 … (ENGL1113)` → ENGL 1113).
- **Course Search fallback** for a failed schedule export isn't built: no recorded selectors yet. Record that path with codegen if we need it.
- **Degree map data quirks:** SAU's gen ed page lists MATH 2124 Applied Calculus while the CS major lists MATH 2125; one page likely has a typo. A program note that names a required course (e.g. AGEC 2073 for Poultry Science) is loaded on the gen ed block and flagged, because the page doesn't say which area it fills.
- **One-time calendar events:** events have a weekday but no date, so `recurrence: none` is treated like weekly by the checker. Dated events would need a `date` column (a contract change).
- **Node version:** `frontend/.mise.toml` says Node 22; the demo laptop runs Node 26 LTS (installed Nov 18) and both build. Pick one for the team.
- **Electives in a real audit:** how mySAU lists elective options (a list, a pattern like `CSCI 3XXX`, or text) is unknown until the next Connect mySAU as user 4 or 5.

## Semester 2 (parked, don't build before Dec 7)

Kept here so these aren't lost. They come back when the real product starts:
- **Multi-tenancy:** `institution_id` on every table, taken from the session only; cross-institution access returns 404.
- **Real auth:** server-side sessions in HttpOnly/Secure/SameSite cookies; argon2/bcrypt hashing; login rate limits; roles `student` / `advisor` / `admin`, default-deny.
- **Advisor side:** queue, confirm/deny matching SAU's Jenzabar approval, messaging. Status flow `draft → submitted → approved | denied`.
- **FERPA hardening:** audit log on every read/change of a student record; no personal data in logs; strip identifying info before any LLM call (today Gemini is given the first name, decided Nov 18; revisit); check the LLM provider's no-training/retention terms; encryption at rest; HTTPS only; `/docs` off in production.
- **Jenzabar roadmap:** no access → read-only API → write access. Never use or store student credentials. The only behind-login automation is the student-run mySAU connect (Nov 17), which a real integration should replace.
- **mySAU connect hosting:** the connect browser opens on the machine running the backend. That works on the demo laptop, not on a server. Hosted, it needs a different design (a browser extension, a student-side helper, or the Jenzabar API).
- **Other:** multiple schools and branding, complex degree rules, deployment, WCAG 2.1 AA accessibility.
