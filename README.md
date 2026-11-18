# Flowsaic

Course scheduling and advising for Southern Arkansas University students: the catalog, your degree map and a conflict-checking weekly calendar in one place, plus Flow, an AI advisor.

Contributors: Aaron Ezell, Andy Hua, Victor Santamaria. Supervisor: Dr. Ahmad Al-Shami.

## Run Flowsaic on your Windows laptop

You need Windows 10 or 11, an internet connection, about 10 GB free, and permission to install programs. The first setup takes 15–30 minutes, mostly downloads. After that, starting takes about 15 seconds.

1. **Get the code.** Install [Git](https://git-scm.com/download/win) or [GitHub Desktop](https://desktop.github.com/), then clone `huaandy/Flowsaic` (a private repo; ask Andy for access). Use the branch Victor tells you to.
2. **Get the `.env` file from Victor** (privately, never in a public place). Put it in the `Flowsaic` folder, next to `setup.cmd`. It holds the Gemini key: never commit it and never paste it into an AI chat.
3. **Double-click `setup.cmd`.** It installs what's missing (uv, Node.js, and Docker Desktop if needed), then the app's packages, the database and all the data. Press Enter to accept each suggested answer.
   - **If it just installed Docker Desktop**, it stops and lists three steps: restart Windows, open Docker Desktop once and accept its terms (no account needed), then double-click `setup.cmd` again.
   - **It's safe to run again** any time something went wrong; it picks up where it left off.
   - It ends with **"All set!"** and a self-test.
4. **Double-click `start.cmd`.** It starts everything, and your browser opens **http://localhost:8443/** by itself. Keep that black window open while you use Flowsaic; close it (or press Ctrl+C) to stop.
5. **Sign in** with one of these usernames and **any password**:

| Username | Who | Good for |
| --- | --- | --- |
| `1` | Alex Rivera, Computer Science junior | The main demo: conflicts, a full section, missing prereqs |
| `2` | Jordan Brooks, Business freshman | A first-year student |
| `3` | Sam Okafor, Psychology senior | Close to graduating, a failed course being retaken |
| `4` | Returning student | Connect mySAU with your own SAU account; keeps what it loads |
| `5` | New student | Same, but emptied every time you sign in or out |

All of the data stays on your own laptop. Each teammate has their own database.

## Troubleshooting

Each red line in the black window says what to do; do that and run the same file again. The common ones:

- **"Windows protected your PC"** (only if you downloaded a ZIP instead of cloning): click **More info**, then **Run anyway**.
- **Docker won't start, or mentions WSL or virtualization:** restart Windows, open Docker Desktop, and wait until it says **Engine running**. If it asks to install or update WSL, say yes. Then run the file again.
- **"uv isn't available" or "Node.js isn't available" right after installing it:** close the window and double-click the file again (a new window picks up the new program).
- **"Something else is using port 8000"** (or 8443): close the other program, or run `start.cmd -Port 8001` (or `start.cmd -FrontendPort 8444`) from a terminal in the Flowsaic folder.
- **The page says "Can't reach Flowsaic":** the backend is still starting. Wait a few seconds and refresh. If it stays, look at the black window for a red line.
- **"There's no .env file" or Flow says it isn't set up:** the `.env` from Victor is missing or not in the `Flowsaic` folder. Check that it's named exactly `.env` (Windows sometimes saves it as `env` or `.env.txt`; setup fixes that if you run it again).
- **"Flowsaic's data isn't loaded yet":** setup didn't finish. Double-click `setup.cmd` and let it reach "All set!".
- **Red "proxy error ... ECONNREFUSED" lines right after start:** harmless. The front end is ready a few seconds before the backend; they stop on their own.

## For developers

Everything else (architecture, rules for AI assistants, the API, data loading, decisions) is in [AGENTS.md](AGENTS.md). Live API docs are at http://127.0.0.1:8000/docs while Flowsaic runs.
