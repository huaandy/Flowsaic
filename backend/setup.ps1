<#
  Flowsaic backend setup for Windows.
  Double-click setup.cmd in the Flowsaic folder (it runs this file).

  Checks your tools and your .env file, starts the database, installs everything
  (Chromium included) and loads all the data. Safe to run again: every step updates
  what's already there instead of duplicating it. It never prints secret values.

  Optional switches (for running without questions):
    -Schedule live|saved|keep   live = from mySAU (you sign in), saved = the Nov 16 file,
                                keep = leave what's loaded
    -ResetUsers yes|no          yes = recreate the demo users and empty user 4
#>
param(
    [ValidateSet("ask", "live", "saved", "keep")] [string]$Schedule = "ask",
    [ValidateSet("ask", "yes", "no")] [string]$ResetUsers = "ask"
)

# Native tools (uv, docker) write progress to stderr; never treat that as a failure.
# Every step checks the exit code instead.
$ErrorActionPreference = "Continue"
$Backend = $PSScriptRoot
$Repo = Split-Path $Backend -Parent
Set-Location $Backend

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "   OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "   !   $text" -ForegroundColor Yellow }
function Stop-Setup($text) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $text" -ForegroundColor Red
    Write-Host "Fix that, then run setup.cmd again. Send Victor the red line if you're stuck."
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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-Setup "Docker Desktop isn't installed. Install it from https://www.docker.com/products/docker-desktop/ and open it once."
}
if (-not (Test-Docker)) {
    $dockerApp = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerApp) {
        Write-Host "   Starting Docker Desktop..."
        Start-Process $dockerApp
    }
    Write-Host "   Waiting for Docker (up to 3 minutes)..."
    $deadline = (Get-Date).AddMinutes(3)
    while (-not (Test-Docker)) {
        if ((Get-Date) -gt $deadline) {
            Stop-Setup "Docker isn't running. Open Docker Desktop and wait until it says 'Engine running'."
        }
        Start-Sleep -Seconds 3
    }
}
Ok "Docker is running"

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
    Warn "No Gemini API key. Flow (the AI advisor) and course search need one; Victor has it."
    $secure = Read-Host "   Paste the Gemini API key (or press Enter to skip)" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if ($plain) { Add-EnvSetting "GEMINI_API_KEY" $plain.Trim(); Ok "Saved the key in $envTarget" }
}
if (-not (Get-EnvValue "GEMINI_MODEL")) {
    $model = Read-Host "   Gemini model name, as in Victor's .env (or press Enter to skip)"
    if ($model) { Add-EnvSetting "GEMINI_MODEL" $model.Trim(); Ok "Saved the model name" }
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
Step "4/7  Installing Flowsaic (packages, tables, Chromium)"
uv sync
if ($LASTEXITCODE -ne 0) { Stop-Setup "Installing the Python packages failed (uv sync)." }
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Stop-Setup "Building the database tables failed (alembic upgrade head)." }
uv run playwright install chromium
if ($LASTEXITCODE -ne 0) { Stop-Setup "Installing Chromium failed (playwright install chromium)." }
Ok "Packages, tables and Chromium are installed"

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
        if (Ask "Load it live from mySAU? A browser opens and you sign in with your SAU account." $true) { $choice = "live" }
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

$counts = Get-Counts
$reset = $ResetUsers -eq "yes"
if ($counts["students"] -eq 0) {
    $reset = $true
} elseif ($ResetUsers -eq "ask") {
    $reset = Ask "Sign-in users already exist. Recreate them? (This also empties user 4 and removes any mySAU data on it.)" $false
}
if ($reset) {
    uv run python ..\db\scripts\seed_demo.py
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Creating the sign-in users failed." }
    Ok "Sign-in users 1-4 are ready"
} else {
    Ok "Kept the existing sign-in users"
}

# --- 7. Final check -----------------------------------------------------------------------------
Step "7/7  Final check"
uv run python ..\db\scripts\check_db.py
if ($LASTEXITCODE -ne 0) { Stop-Setup "The database check failed." }
$counts = Get-Counts
Ok ("Loaded: {0} sections, {1} courses ({2} searchable), {3} degree plans, {4} sign-in users" -f `
    $counts["sections"], $counts["courses"], $counts["embedded"], $counts["degree_plans"], $counts["students"])

Write-Host ""
Write-Host "All set! Double-click start.cmd to run Flowsaic." -ForegroundColor Green
Write-Host "Then sign in at http://127.0.0.1:8000/ as 1, 2, 3 or 4 (any password)."
