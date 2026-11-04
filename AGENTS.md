# AGENTS.md — Flowsaic

Shared rules for every AI coding tool on this team and every teammate. Cursor reads this file automatically, and Claude Code reads it through `CLAUDE.md`. ChatGPT doesn't read files on its own, so paste this file into a ChatGPT Project's instructions or at the start of a chat. **If this file and your AI disagree, this file wins.**

The source of truth for data and API shapes is the team's **Flowsaic Data & API Contracts** doc. If this file and the doc disagree, the doc wins. Fix this file.

## Project

Flowsaic is a web app for course scheduling and advising. Students combine the course catalog, their degree map, and a conflict-checking calendar into one schedule, then submit it to their advisor, who confirms or denies it. Launching at Southern Arkansas University (SAU) first. Test data: SAU's section export from IT, plus the Agricultural Science: Poultry Science, BS degree plan. **All student data is fake.**

Flowsaic is a web application with a REST API backend. It is not itself an API.

**This system will handle FERPA-protected student education records.** FERPA governs access and contracts, not code, but institutions will review us (HECVAT questionnaire, security review). Write every line as if it will be audited.

## Owners

| Area | Owner | AI tool |
| --- | --- | --- |
| Backend (Python/FastAPI) | Victor | Claude Code |
| Front end | Andy | Cursor / ChatGPT |
| Database | Aaron | Cursor / ChatGPT |
| AI advisor + constraint solver | Deferred until Tabs 1–3 work | — |

Don't change another owner's area without telling them.

## Product direction

- **The value:** students today juggle 3 tabs (academic calendar, degree map, course catalog/class schedule) and piece a schedule together by hand. Flowsaic puts them in one place: a "mosaic" of those tools.
- **SAU first.** Keep `institution_id` everywhere (cheap), but no multi-school branding/admin work until a second school exists.
- **SAU's system of record is Jenzabar** (student records, registration, financial aid, billing). Flowsaic sits *on top of* Jenzabar; it never replaces it. Integration roadmap:
  1. **No access (now):** student plans in Flowsaic and gets a ready-to-enter list of exact sections, then registers through SAU's existing portal as usual.
  2. **Read-only API access (needs SAU IT):** pull sections and completed courses from Jenzabar.
  3. **Write access (needs SAU IT + likely Jenzabar's partner program):** submit approved schedules straight into Jenzabar.
- **Never** log into Jenzabar or the SAU portal with a student's credentials, or scrape behind a login. Only official access.
- **Every import records `imported_at`;** the UI shows data age; a failed or empty import alerts staff instead of silently serving stale data.
- **Success metrics:** a student builds a conflict-free, degree-map-valid schedule in ≤10 min manually / ≤5 min with the AI advisor; advisor review ≤5 min.
- **Accessibility:** WCAG 2.1 AA from day one (legally required for public universities under ADA Title II).
- **Out of scope for now:** real-time chat, microservices, SIS integration beyond the Jenzabar roadmap above.
- **Decided:** the team keeps running Flowsaic after graduation. Build with maintainability in mind: docs, tests, simple deploys.

## Stack

FastAPI + Pydantic, SQLAlchemy, Alembic, PostgreSQL (optionally `pg_trgm` for typo-tolerant search), pytest, Docker. OR-Tools CP-SAT for the future scheduler. Front end: _not chosen yet_.
Backend lives in `backend/`; entry point `backend/app/main.py`. Run with `uv sync` then `uv run fastapi dev app/main.py` from `backend/`.

## Team workflow

1. **Agree on contracts first.** For each tab, the team agrees on the data model and API inputs/outputs in the contracts doc before anyone builds.
2. **Build in parallel against the contract.** The front end builds against mock JSON shaped exactly like the contract, so it never waits on the backend. The live spec is at `/docs` once the backend runs.
3. **Changing a contract:** propose it to the team, update the contracts doc, update this file, then change code.
4. **Schema ownership:** tables live in the repo as SQLAlchemy models + Alembic migrations, the one source of truth. **Only one person generates and runs migrations.** No hand-written tables outside migrations.

## Rules for any AI assistant

- **Plan before code.** First give a short plan and list the files you'll touch. Wait for the developer's OK.
- **One task at a time.** Do only what was asked. Don't refactor unrelated code or touch another teammate's area unless told to.
- **No new dependencies** without asking and saying why.
- **Tests are part of the task.** Write tests, run them, show the results. A task with failing tests is not done.
- **Never run `git push`, delete files, or drop/reset database tables** without asking first.
- **Explain security-relevant code.** For any auth, permission, or tenancy code, explain in plain words how it prevents unauthorized access.
- **Don't change the contracts** without being told to. If the task seems to need it, stop and say so.
- **Say when you're unsure.** If a requirement is ambiguous or conflicts with this file, stop and ask instead of guessing.
- When finished: summarize what changed and anything to double-check.

## Non-negotiable rules

1. **Multi-tenancy.** Every table has `institution_id`. It comes from the logged-in session only, never from the request body, query string or URL. Every query filters on it.
2. **Cross-institution access returns 404**, never 403, so nobody can probe what exists.
3. **IDs are UUIDs.** SAU's own codes (course code, term code) are normal fields, never primary keys. Never show UUIDs to users.
4. **Auth is server-side sessions** (not JWT). Roles: `student`, `advisor`, `admin`. Permissions are default-deny: an endpoint is closed unless a role is explicitly allowed.
5. **The LLM never decides.** It parses preferences and writes explanation text only. Conflict checks and scheduling are done in code.
6. **Student data (FERPA).** No student data in logs, error messages, test fixtures or commits. Use fake students in tests.
7. **Secrets** live in `.env` only (never committed). `.env.example` lists the keys with placeholder values. Alembic reads the DB URL from settings, never from `alembic.ini`.
8. **Audit log.** Every submit, every advisor decision, and every read or change of a student record writes an `audit_log` row.
9. **Errors** are always `{ "error": "snake_case_code" }` with the matching HTTP status (400, 401, 404, 409, 500). Never return stack traces or raw exceptions.

## Security details

### Tenancy and access control
- Every endpoint enforces its allowed roles through a shared dependency. An endpoint with no explicit permission check is a bug.
- Students access only their own records. Advisors access only their assigned students. Admins access only their own institution.
- Every endpoint has a test proving a user from Institution A cannot read or modify Institution B's data, and a student cannot access another student's data.

### Secrets
- **No secrets in code, ever.** Database URLs, API keys, session secrets, and LLM keys come from environment variables.
- **Never paste `.env` contents or real keys into any AI chat** (Claude, ChatGPT, Cursor). Use placeholders.
- If a secret is ever committed: tell the team and rotate it immediately. Deleting the commit isn't enough; it stays in git history.

### Student data
- **No real student data anywhere**: not in code, tests, seed files, fixtures, logs, or AI prompts. Generate fake students (e.g. with Faker).
- **Never log personal data** (names, emails, student IDs, schedules, message contents). Log internal IDs and event types only.
- **LLM boundary:** strip all identifying information before any LLM call. The LLM receives preferences and course data only, never who the student is.

### Auth
- Sessions in HttpOnly, Secure, SameSite cookies (revocable instantly).
- Passwords hashed with argon2 (or bcrypt). Never stored or logged in plaintext.
- Rate-limit login attempts. Sessions expire.

### Input and queries
- All input validated by Pydantic models; reject unknown fields (`extra="forbid"`).
- SQLAlchemy parameterized queries only. **No f-string or string-concatenated SQL.**
- Enforce pagination limits (max page size). Use SQL for filtering, search, and pagination.

### Front end
- Never store session data or personal data in `localStorage`; the session lives in an HttpOnly cookie.
- Never trust the front end for security. Hiding a button is not access control; the backend enforces every permission.
- Never render user-supplied text as raw HTML (XSS).

### Transport and deployment (later)
- HTTPS only. Database encrypted at rest.
- CORS restricted to our front-end origin, never `*`.
- FastAPI's `/docs` disabled in production.

## Formats

- Times: 24-hour `HH:MM`. Timestamps: ISO 8601 UTC.
- Days: letters from `MTWRFSU` (R = Thursday).
- JSON fields: `snake_case`. Missing values are `null`, not omitted.

## Data model

One course has many sections; one section has one or more meetings (lecture plus lab). Conflict checks run on meetings. Every table also has `id` (UUID) and `institution_id`.

| Table | Fields | Unique on |
| --- | --- | --- |
| `term` | code, name | institution + code |
| `course` | code, title, department, credits, description, prerequisites (JSON tree) | institution + code |
| `section` | course_id, term_id, section_number (text), instructor, division (UG/GR), location, enrolled, capacity | course + term + section_number |
| `meeting` | section_id, days, start_time, end_time, building, room | — |
| `degree_map` | name, catalog_year | institution + name + year |
| `degree_map_course` | degree_map_id, course_id, requirement_group, recommended_semester | map + course |
| `user` | email, role, degree_map_id (students only) | institution + email |
| `completed_course` | student_id, course_id, source (transcript or manual) | student + course |
| `schedule` | student_id, term_id, status, advisor_id, submitted_at, decided_at | — |
| `schedule_section` | schedule_id, section_id | schedule + section |
| `message` | schedule_id, sender_id, body, sent_at | — |
| `audit_log` | user_id, action, target_type, target_id, at | — |

`seats_open = capacity - enrolled` (floored at 0) is computed on read, never stored.

Prerequisites: SAU lists a single course code (e.g. `CSCI 3130`). Store as `{"and": ["CSCI 3130"]}`; no prerequisite is `null`. Keep the tree format so multiple prerequisites can be added later.

### Completed courses
No SIS integration, so completed courses are **student-reported**: the student checks them off on their degree map, or uploads an unofficial transcript PDF that the backend parses and the student confirms. **The uploaded transcript file is never stored** (parse in memory, keep only the confirmed list) and never sent to the LLM.

## Import: SAU section export (Excel)

One row = one section of a course in one term. Read 15 of 16 columns; skip **Concurrent**.

| Column | Field | Rule |
| --- | --- | --- |
| Course code | `course.code` + `section.section_number` | Last token after a space is the section (`001`, `002L`, `001H`); the rest is the course code. Insert a missing space (`SCM6003` → `SCM 6003`). Reject rows that don't fit. |
| Title | `course.title` | Required |
| Term | `term.code`, `term.name` | Required |
| Institutional | `course.department` | Required |
| Begin / End | `meeting.start_time` / `end_time` | HH:MM; End after Begin; blank only for online/TBA |
| Days | `meeting.days` | MTWRFSU letters; blank = no set time |
| Location | `section.location` | Main campus, online, etc. |
| Building / Room | `meeting.building` / `room` | Optional |
| Instructor | `section.instructor` | Blank → "Staff" |
| DIV | `section.division` | `UG` or `GR` only |
| Credit | `course.credits` | Fixed whole number |
| ENR / CAP | `section.enrolled` / `capacity` | Integers ≥ 0 |

Re-imports update sections in place (matched on course + term + section_number). Rejected rows are reported, not guessed.
Descriptions and prerequisites come from SAU's public catalog search, matched on course code. The degree map comes from the Poultry Science degree plan.

## API

All endpoints need a session and are scoped to the user's institution.

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/admin/imports/sections` | admin | Upload the Excel export |
| GET | `/catalog/terms` | any | Term dropdown |
| GET | `/catalog/courses` | any | Search/filter (`term` required; `search`, `department`, `on_degree_map`, `page`) |
| GET | `/catalog/courses/{course_id}` | any | Course detail with sections and meetings |
| GET | `/schedules` | student | My schedules |
| POST | `/schedules` | student | Start a draft |
| PUT | `/schedules/{id}/sections` | student | Replace a draft's sections; returns conflicts and warnings |
| POST | `/schedules/{id}/submit` | student | Send to advisor |
| GET | `/advisor/queue` | advisor | Submitted schedules waiting on me |
| POST | `/schedules/{id}/decision` | advisor | `{ "decision": "confirm" \| "deny", "note": "optional" }` |
| GET/POST | `/schedules/{id}/messages` | student, advisor | Read and reply on a schedule |

Exact request/response bodies are in the contracts doc.

Not yet specced (do not invent shapes; spec them in the doc first): login/logout/current user, completed courses, degree progress, preferences, admin user management, AI advisor.

## Schedule rules

- Status flow: `draft → submitted → approved | denied`. Editing a denied schedule moves it back to `draft`.
- Only a draft can be edited.
- Conflict: two meetings share a day and `start_a < end_b and start_b < end_a`.
- Conflicts and full sections come back as warnings while building. **Both block submission** (`409 has_conflicts` / `409 section_full`).
- The advisor decision is one confirm or deny, matching SAU's Jenzabar approval. A note on a deny is posted as a message.

## Build order

Build **tab by tab** (vertical slices): agree contracts → build in parallel → integrate → demo → merge → next tab. Every few tabs, run a security review against this file and list every violation with file and line before fixing anything.

### Step 0: Foundation
1. ✅ Project structure, config from env vars, `.env.example`, `.gitignore`
2. ✅ Database connection + Alembic set up, pytest running
3. Auth: login, password hashing, roles, `institution_id` from session
4. A shared permission dependency every route uses
5. Audit log table + helper
6. Generic error handling (no internals leaked)

### Tabs
1. **Browse Catalog** ← CURRENT (schema + migrations, import SAU data, three catalog endpoints, tests)
2. Schedule Builder + conflict checking
3. Submit + advisor review
4. Preferences + AI advisor
5. Admin + branding (deferred until a second school exists)

Tabs 1–3 alone are a working product.

## Definition of done

An endpoint is done when it matches the contracts doc, has tests (including a test that institution A can't see institution B's data), and passes `pytest`.

## Git

- Repo is **private**.
- Everyone works on their own branch (`backend/...`, `frontend/...`, `db/...`). Nothing merges into `main` without a pull request reviewed by one other teammate.
- Check `git status` before every commit. Never commit `.env`, database dumps, real student data, or secrets.
- Ask before pushing.

## Current status
(Each owner updates their line every work session.)
- Repo: private on GitHub (`huaandy/Flowsaic`). Contributors: Aaron Ezell, Andy Hua, Victor Santamaria. Supervisor: Dr. Ahmad Al-Shami.
- Contracts: Data & API Contracts doc sent to the team for review; waiting on feedback.
- Backend: Step 0 items 1–2 done (app layout in `backend/app/`, settings from env vars, `.env.example`, DB engine with no models, Alembic initialized with no migrations, pytest passing). Managed with `uv`, Python 3.14. Next: Step 0 item 3, auth (sessions + password hashing).
- Database: _fill in_
- Front end: _fill in_

## Open questions (don't build around these yet)

- `L`/`H` section suffixes: confirm lab/honors, and how a lab links to its lecture.
- Who pulls descriptions/prerequisites from the catalog site, and whether IT's permission covers it.
- Aaron's shared models vs. this data model: reconcile before the first migration.
- Front-end framework?
- Which LLM provider, and do their data terms allow this use (no training on our data, retention limits)?
