<#
  Flowsaic setup for Windows (backend and React front end).
  Double-click setup.cmd in the Flowsaic folder (it runs this file).

  Checks your tools (uv, Docker, Node.js) and your .env file, starts the database, installs
  everything (Chromium and the front end's packages included) and loads all the data. Safe to run again: every step updates
  what's already there instead of duplicating it. It never prints secret values.

  Optional switches (for running without questions):
    -Schedule live|saved|keep   live = from mySAU (you sign in), saved = the Nov 16 file,
                                keep = leave what's loaded
    -ResetUsers yes|no          yes = put demo users 1-3 back to their demo data (courses, commitments,
                                preferences). User 4 (returning student) keeps its mySAU data either way;
                                user 5 (new student) always starts empty anyway
    -ClearReturning yes|no      yes = clear user 4's mySAU data so you can test a first connect again
                                (default no)
#>
param(
    [ValidateSet("ask", "live", "saved", "keep")] [string]$Schedule = "ask",
    [ValidateSet("ask", "yes", "no")] [string]$ResetUsers = "ask",
    [ValidateSet("ask", "yes", "no")] [string]$ClearReturning = "ask"
)

# Native tools (uv, docker) write progress to stderr; never treat that as a failure.
# Every step checks the exit code instead.
$ErrorActionPreference = "Continue"
$DefaultGeminiModel = "gemini-3.8-flash"  # keep in step with backend/.env.example
$Backend = $PSScriptRoot
$Repo = Split-Path $Backend -Parent
Set-Location $Backend

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "   OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "   !   $text" -ForegroundColor Yellow }
function Stop-Setup($text) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $text" -ForegroundColor Red
    Write-Host "Do what the red line says, then double-click setup.cmd again (it's safe to run as often as you like)."
    Write-Host "Stuck? Find this message under Troubleshooting in README.md (in your Flowsaic folder); it lists the exact steps."
    exit 1
}
function Ask($question, [bool]$default) {
    $hint = "[y/N]"
    if ($default) { $hint = "[Y/n]" }
    $answer = Read-Host "   $question $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $default }
    return $answer.Trim().ToLower().StartsWith("y")
}
function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

# --- 1. Tools ---------------------------------------------------------------------------------
Step "1/7  Checking your tools"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Warn "uv isn't installed. It runs Python and installs Flowsaic's packages."
    if (Ask "Install uv now (official installer from astral.sh)?" $true) {
        powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Stop-Setup "uv isn't available. Close this window, open a new one and run setup.cmd again."
    }
}
Ok ((uv --version) | Out-String).Trim()

# Docker Desktop runs the database. Just installed? Its command isn't on this window's PATH yet.
$dockerApp = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
$dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $dockerBin "docker.exe"))) {
    $env:Path = "$dockerBin;$env:Path"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Warn "Docker Desktop isn't installed. Flowsaic's database runs in it."
    if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Ask "Install Docker Desktop now (winget, official package; Windows asks for permission)?" $true)) {
        winget install --id Docker.DockerDesktop --exact --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Docker Desktop is installed. Three one-time steps before Flowsaic can use it:" -ForegroundColor Yellow
            Write-Host "  1. Restart Windows (Docker needs it the first time)."
            Write-Host "  2. Open Docker Desktop from the Start menu, accept its terms (no account needed, you can skip sign-in)"
            Write-Host "     and wait until it says 'Engine running'. If it asks to install or update WSL, say yes."
            Write-Host "  3. Double-click setup.cmd again."
            exit 0
        }
    }
    Stop-Setup "Docker Desktop isn't installed. Get it from https://www.docker.com/products/docker-desktop/ (Download for Windows), install it, restart Windows and open Docker Desktop once."
}
if (-not (Test-Docker)) {
    if (Test-Path $dockerApp) {
        Write-Host "   Starting Docker Desktop..."
        Start-Process $dockerApp
    }
    Write-Host "   Waiting for Docker (up to 5 minutes). The first time, Docker Desktop asks you to accept its terms: do that in its window."
    $deadline = (Get-Date).AddMinutes(5)
    while (-not (Test-Docker)) {
        if ((Get-Date) -gt $deadline) {
            Stop-Setup "Docker isn't running. Open Docker Desktop, accept its terms if asked, and wait until it says 'Engine running'. If it reports a WSL or virtualization problem, restart Windows first."
        }
        Start-Sleep -Seconds 3
    }
}
Ok "Docker is running"

# Node.js runs the React front end (Vite). winget installs it to Program Files; a window opened
# before that install doesn't have it on PATH yet, so look there too.
$nodeDir = Join-Path $env:ProgramFiles "nodejs"
if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $nodeDir "npm.cmd"))) { $env:Path = "$nodeDir;$env:Path" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Warn "Node.js isn't installed. It runs the Flowsaic front end."
    if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Ask "Install Node.js LTS now (winget, official package)?" $true)) {
        winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
        $env:Path = "$nodeDir;$env:Path"
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Stop-Setup "Node.js isn't available. Install the LTS version from https://nodejs.org/ (the big green button), close this window, then run setup.cmd again."
    }
}
Ok ("Node.js " + ((node --version) | Out-String).Trim())

# --- 2. .env -----------------------------------------------------------------------------------
Step "2/7  Checking your .env file"
$envBackend = Join-Path $Backend ".env"
$envRoot = Join-Path $Repo ".env"
# Windows often renames the file when it's saved or downloaded: ".env.txt" (Notepad),
# or "env" / "env.txt" (the leading dot dropped). Put it back to ".env".
foreach ($dir in @($Backend, $Repo)) {
    if (Test-Path (Join-Path $dir ".env")) { continue }
    foreach ($wrong in @(".env.txt", "env", "env.txt")) {
        $candidate = Join-Path $dir $wrong
        if (Test-Path $candidate -PathType Leaf) {
            Rename-Item $candidate ".env"
            Ok "Renamed '$wrong' to '.env' in $dir"
            break
        }
    }
}
# Both places work; backend\.env wins for any setting it has.
$envFiles = @(@($envRoot, $envBackend) | Where-Object { Test-Path $_ })
if ($envFiles.Count -eq 0) {
    Warn "No .env file found, so I'm making backend\.env from .env.example."
    # Leave out the example's placeholder values so they can never override a real setting.
    $lines = [System.IO.File]::ReadAllLines((Join-Path $Backend ".env.example")) |
        Where-Object { $_ -notmatch "^\s*(GEMINI_API_KEY|SECRET_KEY)\s*=" -and $_ -notmatch "^\s*GEMINI_MODEL\s*=\s*$" }
    [System.IO.File]::WriteAllLines($envBackend, $lines, (New-Object System.Text.UTF8Encoding($false)))
    $envFiles = @($envBackend)
}
# Python can't read a .env saved as "Unicode" (UTF-16) or with a byte-order mark.
foreach ($file in $envFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($file)
    $utf16 = ($bytes.Length -ge 2) -and ((($bytes[0] -eq 0xFF) -and ($bytes[1] -eq 0xFE)) -or (($bytes[0] -eq 0xFE) -and ($bytes[1] -eq 0xFF)))
    $bom = ($bytes.Length -ge 3) -and ($bytes[0] -eq 0xEF) -and ($bytes[1] -eq 0xBB) -and ($bytes[2] -eq 0xBF)
    if ($utf16 -or $bom) {
        $text = [System.IO.File]::ReadAllText($file)
        [System.IO.File]::WriteAllText($file, $text, (New-Object System.Text.UTF8Encoding($false)))
        Ok "Re-saved $file as plain UTF-8 (it was saved in a format Python can't read)"
    }
}
$envTarget = $envFiles[-1]   # where missing settings get added

function Get-EnvValue($name) {
    $value = $null
    foreach ($file in $envFiles) {
        foreach ($line in [System.IO.File]::ReadAllLines($file)) {
            if ($line -match "^\s*$name\s*=\s*(.*)$") { $value = $Matches[1].Trim().Trim('"').Trim("'") }
        }
    }
    return $value
}
function Add-EnvSetting($name, $value) {
    [System.IO.File]::AppendAllText($envTarget, "`r`n$name=$value`r`n")
}

if (-not (Get-EnvValue "DATABASE_URL")) {
    $example = [System.IO.File]::ReadAllLines((Join-Path $Backend ".env.example")) | Where-Object { $_ -match "^DATABASE_URL=" } | Select-Object -First 1
    $exampleValue = $example.Substring("DATABASE_URL=".Length)
    Add-EnvSetting "DATABASE_URL" $exampleValue
    Ok "Added DATABASE_URL (the local Docker database, same for everyone)"
}
$key = Get-EnvValue "GEMINI_API_KEY"
if ((-not $key) -or ($key -eq "your-gemini-api-key")) {
    Warn "No Gemini API key. Flow (the AI advisor) and course search need one."
    Write-Host "   If your .env has one, copy the text after GEMINI_API_KEY= and paste it below."
    Write-Host "   No key? Get a free one: open https://aistudio.google.com/apikey, sign in with Google,"
    Write-Host "   click 'Create API key' and copy it. (Enter skips it; run setup again later to add it.)"
    $secure = Read-Host "   Paste the Gemini API key (or press Enter to skip)" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if ($plain) { Add-EnvSetting "GEMINI_API_KEY" $plain.Trim(); Ok "Saved the key in $envTarget" }
}
if (-not (Get-EnvValue "GEMINI_MODEL")) {
    # The model Flowsaic is built and tested with; nothing to look up.
    Add-EnvSetting "GEMINI_MODEL" $DefaultGeminiModel
    Ok "Added GEMINI_MODEL=$DefaultGeminiModel to $envTarget"
}
$key = Get-EnvValue "GEMINI_API_KEY"
$hasKey = [bool]$key -and ($key -ne "your-gemini-api-key")
if ($hasKey) { Ok ".env is ready" } else { Warn ".env works, but without a Gemini key the AI parts won't" }

# --- 3. Database ---------------------------------------------------------------------------------
Step "3/7  Starting the database"
# The database container is shared by every copy of the repo on this laptop. If it already
# exists (from this folder or another clone), just make sure it's running.
cmd /c "docker container inspect flowsaic-db >nul 2>&1"
if ($LASTEXITCODE -eq 0) {
    docker start flowsaic-db | Out-Null
    $code = $LASTEXITCODE
} else {
    Push-Location $Repo
    docker compose up -d
    $code = $LASTEXITCODE
    Pop-Location
}
if ($code -ne 0) {
    Stop-Setup "Docker couldn't start the database (see the message above). If it mentions port 5433, something else is using that port."
}
Write-Host "   Waiting for the database to be ready..."
$deadline = (Get-Date).AddMinutes(2)
do {
    $health = (docker inspect -f "{{.State.Health.Status}}" flowsaic-db) | Out-String
    if ($health.Trim() -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($health.Trim() -ne "healthy") { Stop-Setup "The database didn't become ready. Check Docker Desktop for the flowsaic-db container." }
Ok "Database is up (flowsaic-db)"

# --- 4. Packages, tables, Chromium ------------------------------------------------------------
Step "4/7  Installing Flowsaic (packages, tables, Chromium, front end)"
uv sync
if ($LASTEXITCODE -ne 0) { Stop-Setup "Installing the Python packages failed (uv sync)." }
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Stop-Setup "Building the database tables failed (alembic upgrade head)." }
uv run playwright install chromium
if ($LASTEXITCODE -ne 0) { Stop-Setup "Installing Chromium failed (playwright install chromium)." }
Push-Location (Join-Path $Repo "frontend")
npm install --no-audit --no-fund
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Stop-Setup "Installing the front end's packages failed (npm install in frontend)." }
Ok "Packages, tables, Chromium and the front end are installed"

function Get-Counts {
    $counts = @{}
    foreach ($line in (uv run python ..\db\scripts\status.py)) {
        if ($line -match "^(\w+)=(\d+)$") { $counts[$Matches[1]] = [int]$Matches[2] }
    }
    return $counts
}
$counts = Get-Counts

# --- 5. Course schedule -----------------------------------------------------------------------
Step "5/7  This term's course schedule"
$choice = $Schedule
if ($choice -eq "ask") {
    if ($counts["sections"] -gt 0) {
        $choice = "keep"
        if (Ask "Already loaded ($($counts['sections']) sections). Refresh it live from mySAU?" $false) { $choice = "live" }
    } else {
        $choice = "saved"
        Write-Host "   The saved Spring 2027 schedule (in the repo) is enough to run and demo Flowsaic."
        if (Ask "Load the newest one live from mySAU instead? A browser opens and you sign in with your own SAU account." $false) { $choice = "live" }
    }
}
if ($choice -eq "live") {
    Write-Host "   A Chromium window will open. Sign in to mySAU yourself (Microsoft + Duo); you have 5 minutes."
    uv run python ..\db\scripts\connect_mysau.py
    if ($LASTEXITCODE -eq 0) {
        Ok "Loaded the live course schedule"
    } else {
        Warn "Couldn't load it live (the reason is on the line above). Using the saved Nov 16 schedule instead."
        $choice = "saved"
    }
}
if ($choice -eq "saved") {
    uv run python ..\db\scripts\import_sections.py
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Loading the saved course schedule failed." }
    Ok "Loaded the saved course schedule (Nov 16)"
}
if ($choice -eq "keep") { Ok "Kept the schedule that's already loaded" }

# --- 6. Courses, degree plans, users ------------------------------------------------------------
Step "6/7  Course descriptions, degree plans and sign-in users"
if ($hasKey) {
    uv run python ..\db\scripts\scrape_course_info.py
    if ($LASTEXITCODE -eq 0) {
        Ok "Courses loaded and course search is ready"
    } else {
        Warn "Courses loaded, but course search (embeddings) failed; see above. Run setup.cmd again later to retry."
    }
} else {
    uv run python ..\db\scripts\load_course_info.py
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Loading the course descriptions failed." }
    Warn "Courses loaded without course search (no Gemini key)"
}
uv run python ..\db\scripts\scrape_degree_maps.py --offline
if ($LASTEXITCODE -ne 0) { Stop-Setup "Loading the degree plans failed." }
Ok "Degree plans loaded"

# Users 1-3 are demo students. User 4 is a returning student: it keeps what Connect mySAU
# loaded. User 5 is a new student: it is emptied at every startup, sign-in and sign-out, so
# it always starts empty without any help from setup.
$counts = Get-Counts
$firstTime = $counts["students"] -eq 0
$reset = $ResetUsers -eq "yes"
$clear = $ClearReturning -eq "yes"
if ($firstTime) {
    $reset = $true
    $clear = $false
} else {
    if ($ResetUsers -eq "ask") {
        Write-Host "   Users 1-3 are demo students. User 4 (returning student) keeps its mySAU data."
        Write-Host "   User 5 (new student) always starts empty, so it never needs resetting."
        $reset = Ask "Put demo users 1-3 back to their demo data (courses, commitments, preferences)?" $false
    }
    if ($ClearReturning -eq "ask") {
        $clear = Ask "Clear user 4's mySAU data so you can test a first connect again?" $false
    }
}
if ($clear) {
    uv run python ..\db\scripts\seed_demo.py --clear-returning
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Creating the sign-in users failed." }
    Ok "Sign-in users 1-5 are ready; user 4's mySAU data was cleared"
} elseif ($reset) {
    uv run python ..\db\scripts\seed_demo.py
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Creating the sign-in users failed." }
    Ok "Sign-in users 1-5 are ready (user 4 kept its mySAU data)"
} else {
    Ok "Kept the existing sign-in users (user 4 kept its mySAU data)"
}

# --- 7. Final check -----------------------------------------------------------------------------
Step "7/7  Final check"
uv run python ..\db\scripts\check_db.py
if ($LASTEXITCODE -ne 0) { Stop-Setup "The database check failed." }
$counts = Get-Counts
Ok ("Loaded: {0} sections, {1} courses ({2} searchable), {3} degree plans, {4} sign-in users" -f `
    $counts["sections"], $counts["courses"], $counts["embedded"], $counts["degree_plans"], $counts["students"])

# Self-test (about 15 seconds): the backend's tests (no database, no Gemini) and the front end's
# type check. A broken install shows up here, not in the middle of a demo.
Write-Host "   Self-test: backend tests and front-end type check..."
uv run pytest -q -p no:cacheprovider 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "   $_" }
$testsOk = $LASTEXITCODE -eq 0
Push-Location (Join-Path $Repo "frontend")
npm run --silent typecheck 2>&1 | Out-Null
$typesOk = $LASTEXITCODE -eq 0
Pop-Location
if ($testsOk -and $typesOk) {
    Ok "Self-test passed"
} else {
    Warn "Part of the self-test failed (backend tests: $testsOk, front end: $typesOk). Flowsaic often still runs with start.cmd."
    Write-Host "   To fix it: close this window and double-click setup.cmd again. If it still fails, get the newest"
    Write-Host "   version (GitHub Desktop: Fetch origin, then Pull origin; or 'git pull' in the Flowsaic folder) and run setup again."
}

Write-Host ""
Write-Host "All set! Double-click start.cmd to run Flowsaic." -ForegroundColor Green
Write-Host "Your browser opens http://localhost:8443/. Sign in as 1, 2, 3, 4 or 5 (any password)."
