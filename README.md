# Flowsaic

Course scheduling and advising for Southern Arkansas University students: the catalog, your degree map and a conflict-checking weekly calendar in one place, plus Flow, an AI advisor.

Contributors: Aaron Ezell, Andy Hua, Victor Santamaria. Supervisor: Dr. Ahmad Al-Shami.

## Run Flowsaic on your Windows laptop

You need Windows 10 or 11, an internet connection, about 10 GB free, and permission to install programs. The first setup takes 15–30 minutes, mostly downloads. After that, starting takes about 15 seconds.

### 1. Get the code

**With GitHub Desktop (easiest):**
1. Install [GitHub Desktop](https://desktop.github.com/) and sign in with your GitHub account.
2. Click **File > Clone repository**, pick **huaandy/Flowsaic** in the list, and click **Clone**. Remember the folder it shows under **Local path**: that's your **Flowsaic folder**.
3. **If Flowsaic isn't in the list:** your GitHub account hasn't joined the repo yet. Open https://github.com/huaandy/Flowsaic/invitations while signed in, click **Accept invitation**, and try step 2 again. Also make sure GitHub Desktop is signed in to that same account (**File > Options > Accounts**).

**With Git (command line):** install [Git](https://git-scm.com/download/win), then in a terminal run `git clone https://github.com/huaandy/Flowsaic.git`.

You're on the `main` branch, which is the one to use.

**Don't put the Flowsaic folder inside a Google Drive (or OneDrive/Dropbox) synced folder.** It would upload your `.env` (a private key) and `data/private` to the cloud, and syncing can lock files while setup runs. GitHub Desktop's default (`Documents\GitHub\Flowsaic`) is fine.

### 2. Put the `.env` file in place

1. In File Explorer, turn on **View > Show > File name extensions**, so you see the real file names.
2. Copy your `.env` file into your **Flowsaic folder**, next to `setup.cmd`.
3. Check its name is exactly **`.env`**: not `env`, `.env.txt` or `env.txt`. If it's one of those, setup renames it for you.
4. Open it with Notepad if you want to check it: it should have lines starting `DATABASE_URL=`, `GEMINI_API_KEY=` and `GEMINI_MODEL=`.

It holds a private key: never commit it, upload it or paste it into an AI chat.

**No `.env` file?** Setup makes one for you and asks for a Gemini API key. To get your own free key: open https://aistudio.google.com/apikey, sign in with a Google account, click **Create API key**, then copy it and paste it into the setup window when it asks.

### 3. Run setup

Double-click **`setup.cmd`** in your Flowsaic folder. A black window opens and works through 7 steps. When it asks a question, press **Enter** to accept the suggested answer.

- **It installs what's missing:** uv (runs Python), Node.js (runs the website) and Docker Desktop (runs the database), then Flowsaic's packages, the database and all the data. Windows may ask for permission; click **Yes**.
- **If it just installed Docker Desktop**, it stops and lists three one-time steps. Restart Windows. Open **Docker Desktop** from the Start menu, accept its terms (you can skip signing in; no account is needed), and wait until it says **Engine running**; if it asks to install or update WSL, click yes. Then double-click `setup.cmd` again.
- **When it's done** it says **"All set!"** after a self-test. Press any key to close the window.
- **Running it again is always safe.** If anything goes wrong, fix what the red line says and double-click `setup.cmd` again; it picks up where it left off.
- **Questions about the sign-in users** (only when they already exist; Enter = No for both):
  - *"Put demo users 1-3 back to their demo data?"* Yes resets Andy, Aaron and Victor (courses, commitments, preferences). User 4 keeps its mySAU data either way, and user 5 always starts empty anyway.
  - *"Clear user 4's mySAU data so you can test a first connect again?"* Yes empties user 4 (and puts its placeholder name back).
  - To answer without being asked: `setup.cmd -ResetUsers yes -ClearReturning no`.

### 4. Start Flowsaic

Double-click **`start.cmd`**. After about 15 seconds your browser opens **http://localhost:8443/** by itself; if it doesn't, open that address yourself.

Keep the black window open while you use Flowsaic. To stop, close the window (or press Ctrl+C in it). Next time, just double-click `start.cmd` again; you don't need to run setup again.

### 5. Sign in

Use one of these usernames and **any password**:

| Username | Who | Good for |
| --- | --- | --- |
| `1` | Andy Hua, Computer Science junior | The main demo: conflicts, a full section, missing prereqs, a fixed practice that blocks afternoon classes |
| `2` | Aaron Ezell, Business freshman | A first-year student with a morning work shift |
| `3` | Victor Santamaria, Psychology senior | Close to graduating, a failed course being retaken, a part-time job on Tue/Thu |
| `4` | Returning student | Connect mySAU with your own SAU account; keeps what it loads |
| `5` | New student | Same, but emptied every time you sign in or out |

Users 1–3 carry the team's names, but their records (courses, grades, commitments) are made up.

All of the data stays on your own laptop. Each teammate has their own database.

**Submit for approval** (Create Schedule) downloads the saved schedule as a PDF to share with your advisor. Save the schedule first.

### Getting the newest version later

In GitHub Desktop click **Fetch origin**, then **Pull origin** (with Git: run `git pull` in the Flowsaic folder). Then double-click `setup.cmd` once to install anything new, and use `start.cmd` as usual.

## Troubleshooting

Find the message you saw below and follow its steps. After a fix, double-click the same file again.

- **"Windows protected your PC"** (usually only if you downloaded a ZIP instead of cloning): click **More info**, then **Run anyway**.
- **"uv isn't available" or "Node.js isn't available" right after setup installed it:** close the black window and double-click `setup.cmd` again. A new window picks up newly installed programs.
- **Docker won't start, or mentions WSL or virtualization:**
  1. Restart Windows.
  2. Open **Docker Desktop** from the Start menu and wait until it says **Engine running**.
  3. If it says WSL needs installing or updating, let it do so, or open **PowerShell** and run `wsl --update`, then restart again.
  4. If it says virtualization is turned off, it has to be turned on in your laptop's BIOS/UEFI settings. Search the web for "enable virtualization" plus your laptop's brand.
- **"Docker isn't running":** open **Docker Desktop** from the Start menu, wait for **Engine running**, then run the file again.
- **"Something else is using port 5433"** (the database), **8000** or **8443:** another program is using that port.
  - A second copy of Flowsaic left running is the usual cause: close its black window.
  - Or restart Windows.
  - Or use other ports: click the address bar of your Flowsaic folder in File Explorer, type `cmd`, press Enter, and run `start.cmd -Port 8001` (or `start.cmd -FrontendPort 8444`).
- **"There's no .env file":** follow step 2 above. The file has to be in your Flowsaic folder, named exactly `.env`.
- **"No Gemini API key" during setup:** paste the key from your `.env` (the text after `GEMINI_API_KEY=`), or get a free one as described in step 2. Pressing Enter skips it; Flowsaic still runs, but Flow (the AI advisor) won't work until you run setup again with a key.
- **Setup warns that course search failed, or mentions a quota:** a free Gemini key allows about 1,000 course descriptions a day, and Flowsaic has about 1,900. Run `setup.cmd` again the next day; it continues where it stopped.
- **"Flowsaic's data isn't loaded yet":** setup didn't finish. Double-click `setup.cmd` and let it reach "All set!".
- **"Part of the self-test failed":** first close the window and double-click `setup.cmd` again. If it still fails, get the newest version (see **Getting the newest version later**) and run setup again. Flowsaic often still runs with `start.cmd`.
- **The page says "Can't reach Flowsaic":**
  - Make sure the black `start.cmd` window is still open; if you closed it, double-click `start.cmd` again.
  - If it's open, the backend may still be starting: wait 10 seconds and refresh the page.
  - Still there? Close **every** `start.cmd` window (an old one from before a pull can still be running), then double-click `start.cmd` once.
- **Flow says "Flow isn't set up on this laptop yet":** your `.env` has no Gemini model. Double-click `setup.cmd` again; it adds the missing setting. Then close the `start.cmd` window and double-click `start.cmd`.
- **Flow says "Flow can't be reached right now":** check your internet connection and send the message again. If it keeps happening, the Gemini key in your `.env` may be wrong; get a new one (step 2), paste it in place of the old one after `GEMINI_API_KEY=`, and restart `start.cmd`.
- **Red "proxy error ... ECONNREFUSED" lines right after start:** harmless. The website is ready a few seconds before the backend; the lines stop on their own.
- **"The schedule PDF can't be made on this laptop yet":** the browser Flowsaic uses to make PDFs isn't installed. Double-click `setup.cmd` (it installs it), then close the `start.cmd` window and double-click `start.cmd`.
- **Connect mySAU (users 4 and 5) opens a separate browser window:** that's expected. Sign in to mySAU there yourself; you have 5 minutes. Flowsaic never sees your password.
- **Connect mySAU says it failed with "interrupted: the server stopped":** the `start.cmd` window was closed or restarted while you were signing in. Double-click `start.cmd` and click Connect mySAU again.

## For developers

Everything else (architecture, rules for AI assistants, the API, data loading, decisions) is in [AGENTS.md](AGENTS.md). Live API docs are at http://127.0.0.1:8000/docs while Flowsaic runs.

Editing the code? Run `start.cmd -Dev`: the backend restarts whenever you save a `.py` file, and the website runs in its own minimized window. Plain `start.cmd` never restarts by itself, so a running Connect mySAU is never cut off. Don't save `.py` files during a connect in `-Dev` mode.
