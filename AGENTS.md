# Flowsaic — Team Instructions (for every AI tool and every teammate)

This file is the single source of truth for the project. Cursor reads it automatically, and Claude Code reads it through `CLAUDE.md`. ChatGPT doesn't read files on its own, so paste this file into a ChatGPT Project's instructions, or at the start of a chat. **If this file and your AI disagree, this file wins.**

## Project
Flowsaic is AI advisor scheduling/planning software for college students, sold to institutions. It's a team senior project.

| Area | Owner | AI tool |
|---|---|---|
| Backend (Python / FastAPI) | Victor | Claude Code |
| Front end | _teammate_ | Cursor / ChatGPT |
| Database (schema, seed data, indexes) | _teammate_ | Cursor / ChatGPT |
| AI Advisor (LLM preference parsing) | _teammate_ | _fill in_ |

Test data: Southern Arkansas University (SAU) public course catalog and the **Agricultural Science: Poultry Science, BS** degree plan. **All student data is fake.**

**This system will handle FERPA-protected student education records.** FERPA governs access and contracts, not code, but institutions will review us (HECVAT questionnaire, security review). Write every line as if it will be audited.

## Product direction (why we build what we build)
- **The value:** students today juggle 3 tabs (academic calendar, degree map, course catalog/class schedule) and piece a schedule together by hand. Flowsaic puts them in one place: a "mosaic" of those tools.
- **SAU first.** Build for Southern Arkansas University only. Keep `institution_id` everywhere (cheap), but no multi-school branding/admin work until a second school exists.
- **SAU's system of record is Jenzabar** (student records, registration, financial aid, billing). Flowsaic sits *on top of* Jenzabar; it never replaces it. Integration roadmap:
  1. **No access (now):** student plans in Flowsaic and gets a ready-to-enter list of exact sections, then registers through SAU's existing portal as usual.
  2. **Read-only API access (needs SAU IT):** pull sections and completed courses from Jenzabar instead of scraping or self-reporting.
  3. **Write access (needs SAU IT + likely Jenzabar's partner program):** submit approved schedules straight into Jenzabar.
- **Never** log into Jenzabar or the SAU portal with a student's credentials, or scrape behind a login. Only official access.
- **Data import:** catalog, class schedule (sections/times), and academic calendar come from SAU's public website. A staff tab stores source URLs and runs imports, with a CSV upload fallback. Every import records `imported_at`; the UI shows data age; a failed or empty parse alerts staff instead of silently serving stale data.
- **Success metrics:** a student builds a conflict-free, degree-map-valid schedule in ≤10 min manually / ≤5 min with the AI advisor; advisor review ≤5 min. (Confirm the baseline: time the current SAU process.)
- **Accessibility:** WCAG 2.1 AA from day one (legally required for public universities under ADA Title II).

## Scope
- Institutions customize branding, course catalog, degree maps, and course selection dates.
- Students set preferences (job hours, sports, graduate early), then build a schedule manually (catalog + degree map + conflict-checking calendar) or through the AI advisor.
- Finished schedules go to the student's real advisor via built-in messaging (approve / deny / request revision).
- Out of scope: integration with the university's own scheduling software (SIS), real-time chat, microservices.

## Stack
- Backend: FastAPI + Pydantic, SQLAlchemy + Alembic (migrations), pytest
- Database: PostgreSQL (optionally `pg_trgm` for typo-tolerant search)
- Solver: OR-Tools CP-SAT (later)
- Front end: _fill in (framework)_

---

## Team workflow
1. **Agree on contracts first.** For each tab, the team agrees on the data model and the API inputs/outputs before anyone builds. The contracts live in this file.
2. **Build in parallel against the contract.** The front end builds against mock JSON shaped exactly like the API contract, so it never waits on the backend. The live spec is at `/docs` once the backend runs.
3. **Contract changes are announced in the group chat before they're made**, then updated here.
4. **Git:** everyone works on their own branch (`backend/...`, `frontend/...`, `db/...`). Nothing merges into `main` without a pull request reviewed by one other teammate.
5. **Schema ownership:** tables live in the repo as SQLAlchemy models + Alembic migrations, the one source of truth. The DB owner designs the schema, seed data, indexes, and constraints. **Only one person generates and runs migrations.** No hand-written tables outside migrations.

## Rules for any AI assistant
- **Plan before code.** First give a short plan and list the files you'll touch. Wait for the developer's OK.
- **One task at a time.** Do only what was asked. Don't refactor unrelated code or touch another teammate's area (backend / frontend / database) unless told to.
- **No new dependencies** without asking and saying why.
- **Tests are part of the task.** Write tests, run them, show the results. A task with failing tests is not done.
- **Never run `git push`, delete files, or drop/reset database tables** without asking first.
- **Explain security-relevant code.** For any auth, permission, or tenancy code, explain in plain words how it prevents unauthorized access, so the developer can verify it.
- **Don't change the API or data contracts in this file** without being told to. If the task seems to need it, stop and say so.
- **Say when you're unsure.** If a requirement is ambiguous or conflicts with this file, stop and ask instead of guessing.
- When finished: summarize what changed and anything to double-check.

---

## Security rules (non-negotiable, all areas)

### Tenancy and access control
- Every table has `institution_id`, and every query filters by it.
- `institution_id` and the user's role come **only from the authenticated session**. Never from the request body, query string, or URL.
- **Default deny.** Every endpoint enforces its allowed roles through a shared dependency. An endpoint with no explicit permission check is a bug.
- Students access only their own records. Advisors access only their assigned students. Institution admins access only their own institution.
- Requests for another tenant's or user's object return **404**, not 403.
- Every endpoint has a test proving a user from Institution A cannot read or modify Institution B's data, and a student cannot access another student's data.

### Secrets
- **No secrets in code, ever.** Database URLs, API keys, session secrets, and LLM keys come from environment variables.
- `.env` is in `.gitignore`. Commit only `.env.example` with placeholder values.
- **Never paste `.env` contents or real keys into any AI chat** (Claude, ChatGPT, Cursor). Use placeholders.
- If a secret is ever committed: tell the team and rotate it immediately. Deleting the commit isn't enough; it stays in git history.

### Student data
- **No real student data anywhere**: not in code, tests, seed files, fixtures, logs, or AI prompts. Generate fake students (e.g. with Faker).
- **Never log personal data** (names, emails, student IDs, schedules, message contents). Log internal IDs and event types only.
- **LLM boundary:** strip all identifying information before any LLM call. The LLM receives preferences and course data only, never who the student is.
- Error responses never expose stack traces, SQL, file paths, or other tenants' data.
- **Audit log** every read or change of a student record and every advisor decision: who, what, when, which institution.

### Auth
- **Server-side sessions** in HttpOnly, Secure, SameSite cookies (revocable instantly). _(Pending team confirmation.)_
- Passwords hashed with argon2 (or bcrypt). Never stored or logged in plaintext.
- Rate-limit login attempts. Sessions expire.

### Input and queries
- All input validated by Pydantic models; reject unknown fields (`extra="forbid"`).
- SQLAlchemy parameterized queries only. **No f-string or string-concatenated SQL.**
- Enforce pagination limits (max page size).

### Front end
- Never store session data or personal data in `localStorage`; the session lives in an HttpOnly cookie the JavaScript can't read.
- Never trust the front end for security. Hiding a button is not access control; the backend enforces every permission.
- Never render user-supplied text as raw HTML (XSS).

### Transport and deployment (later)
- HTTPS only. Database encrypted at rest.
- CORS restricted to our front-end origin, never `*`.
- FastAPI's `/docs` disabled or protected in production.

### Git hygiene
- Repo is **private**.
- Check `git status` before every commit; never commit `.env`, database dumps, or real data.

---

## Design rules
- **Roles:** student, advisor, institution admin. Every endpoint states who may call it.
- **AI boundary:** the LLM only parses student preferences into structured JSON and writes explanation text. Conflict-free scheduling is done by code (constraint solver), never by the LLM.
- Use SQL for filtering, search, and pagination. Don't reimplement in Python what the database does.

## Data model (core) — DB owner to confirm
- **Institution:** `institution_id`, name, branding settings
- **User:** `user_id`, `institution_id`, role, email, password hash
- **Term:** `term_id` (e.g. `fall2027`), name, registration open/close dates
- **Course:** `course_id`, code (`POUL 3013`), title, credits, description, department, prerequisites
- **Section:** `section_id`, course, term, section number, instructor, room, capacity / seats open
- **Meeting:** belongs to a section; days (`MWF`), start, end. A section can have **multiple meetings** (lecture + lab).
- **Completed course:** student, course, grade, `source` (`manual` | `transcript`), `verified` (bool)
- **Audit log:** actor user_id, institution_id, action, target type + id, timestamp
- Conflict checking happens on **sections**, not courses.
- **Prerequisites** are stored as JSON AND/OR trees:

```python
# "AGRI 1013 AND (BIOL 1014 OR CHEM 1014)"
prereq = {"and": ["AGRI 1013", {"or": ["BIOL 1014", "CHEM 1014"]}]}

def is_met(req, completed: set) -> bool:
    if isinstance(req, str):
        return req in completed
    if "and" in req:
        return all(is_met(r, completed) for r in req["and"])
    if "or" in req:
        return any(is_met(r, completed) for r in req["or"])
```

## Completed courses (decided)
No SIS integration, so completed courses are **student-reported**:
- **Option A:** student checks off completed courses on their degree map.
- **Option B:** student uploads an unofficial transcript PDF → backend extracts course codes + grades → student reviews and confirms the list before it's saved.
- **The uploaded transcript file is never stored.** Parse it in memory, keep only the confirmed list, discard the file. Never send transcript content to the LLM.
- Advisors see unverified courses flagged when reviewing a submitted schedule and can verify them.

---

## Build approach
Build **tab by tab** (vertical slices): agree contracts → build in parallel → integrate → demo → merge → next tab. Every few tabs, run a security review: audit the codebase against the Security rules, list every violation with file and line, and fix nothing until the owner has reviewed the list.

### Step 0: Foundation
1. Project structure, config from env vars, `.env.example`, `.gitignore`
2. Database connection + Alembic set up, pytest running
3. Auth: login, password hashing, roles, `institution_id` from session
4. A shared permission dependency every route uses
5. Audit log table + helper
6. Generic error handling (no internals leaked)

### Tab order
1. **Browse Catalog** ← CURRENT
2. Schedule Builder + conflict checking (interval overlap: same day and `start_a < end_b and start_b < end_a`)
3. Submit to advisor + advisor review (state machine: draft → submitted → approved / denied / revision_requested)
4. Preferences + AI advisor (solver takes structured preference JSON + catalog, returns ranked schedules)
5. ~~Admin + branding~~ (deferred until a second school exists; only the staff data-import tab is needed for SAU)

Tabs 1–3 alone are a working product.

## Tab 1: Browse Catalog — API contract

All endpoints: any logged-in user; `institution_id` comes from their session.

```
GET /catalog/terms
200: { "terms": [{ "term_id": "fall2027", "name": "Fall 2027" }] }
```

```
GET /catalog/courses
Query: term (required), search, department, on_degree_map (bool), page
200: {
  "courses": [
    { "course_id": 101, "code": "POUL 3013", "title": "Poultry Production",
      "credits": 3, "on_degree_map": true, "section_count": 2 }
  ],
  "page": 1, "total": 48
}
400: { "error": "term_required" }
```

```
GET /catalog/courses/{course_id}
Query: term
200: {
  "course_id": 101, "code": "POUL 3013", "title": "Poultry Production",
  "credits": 3, "description": "...",
  "prerequisites": {"and": ["AGRI 1013"]},
  "sections": [
    { "section_id": 5501, "number": "01", "instructor": "Smith",
      "meetings": [{ "days": "MWF", "start": "09:00", "end": "09:50" }],
      "room": "AG 120", "seats_open": 12 }
  ]
}
404: { "error": "course_not_found" }
```

Tab 1 work split:
- **Database:** term/course/section/meeting tables, indexes on `institution_id`, `term`, `department`; seed SAU Poultry Science courses (public data only).
- **Backend:** the three endpoints, search (`ILIKE`, `pg_trgm` optional), max page size, tests incl. cross-institution isolation.
- **Front end:** catalog list, search/filter, course detail view, built against mock JSON matching the contract above.

---

## Current status
(Each owner updates their line every work session.)
- Repo: private on GitHub (`huaandy/Flowsaic`). Contributors: Aaron Ezell, Andy Hua, Victor Santamaria. Supervisor: Dr. Ahmad Al-Shami.
- Backend: Step 0 items 1–2 done (app layout in `backend/app/`, settings from env vars, `.env.example`, DB engine with no models, Alembic initialized with no migrations, pytest passing). Managed with `uv`, Python 3.14. Next: Step 0 item 3, auth (sessions + password hashing).
- Database: _fill in_
- Front end: _fill in_
- AI Advisor: _fill in_

## Open questions
- Who owns the constraint solver: backend or AI Advisor?
- Confirm sessions (vs JWT) for auth.
- Has the DB owner started a schema? Map it to the model above. Who runs migrations?
- Which LLM provider, and do their data terms allow this use (no training on our data, retention limits)?
- Front-end framework?
- What exactly does an SAU advisor do in Jenzabar today: approve a student-submitted schedule, register the student themselves, or release a hold? This decides what Tab 3 must replace.
- **SAU data sources (researched):**
  - Academic calendar: public HTML page with one table per term + a PDF (https://www.saumag.edu/academics/academic-calendar/). Changes once a year, so staff can simply enter the ~20 key dates per term.
  - Catalog: https://www.saumag.edu/academics/catalogs/ (format not yet checked).
  - **Class schedule (sections/times/rooms) lives inside SAU's Jenzabar portal** (my.saumag.edu course search). Open question: are search results visible when logged out? Even if public, get SAU IT's OK before automating queries against it. Realistic fallback: registrar uploads a CSV export of sections each term.
- **Decided:** the team keeps running Flowsaic after graduation. Before any school signs on, we need a legal entity (e.g. an LLC), a support plan for registration weeks, and paid hosting with backups. Build with maintainability in mind: docs, tests, simple deploys.
