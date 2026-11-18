<#
  Start Flowsaic on Windows. Double-click start.cmd in the Flowsaic folder.
  Starts Docker and the database if needed, brings the tables up to date, runs the backend
  (FastAPI) and the React front end (Vite), and opens http://localhost:8443/ when both answer.
  Stop both with Ctrl+C (or close the window).
  If Flowsaic is already running, it reuses what's running instead of starting a second copy.

  Optional:
    -Port 8001          the backend's port (default 8000). The front end follows it.
    -FrontendPort 8444  the front end's port (default 8443)
    -BackendOnly        don't start the front end; opens the backend's test page instead
    -NoBrowser          don't open the browser
    -Dev                for editing the code: the backend reloads when a .py file changes, and the
                        front end runs in its own (minimized) window

  Why no auto-reload by default (Nov 18): on Windows, uvicorn restarts its worker by sending
  Ctrl+C to the whole console window. With Vite in the same window, every reload killed the
  website ("Can't reach Flowsaic") and cut off a running mySAU connect.
#>
param(
    [int]$Port = 8000,
    [int]$FrontendPort = 8443,
    [switch]$BackendOnly,
    [switch]$NoBrowser,
    [switch]$Dev
)
$ErrorActionPreference = "Continue"
$Url = "http://127.0.0.1:$Port/"
$FrontendUrl = "http://localhost:$FrontendPort/"
$Backend = $PSScriptRoot
$Repo = Split-Path $Backend -Parent
$Frontend = Join-Path $Repo "frontend"
Set-Location $Backend

function Stop-Start($text) {
    Write-Host ""
    Write-Host "COULDN'T START: $text" -ForegroundColor Red
    Write-Host "Stuck? Find this message under Troubleshooting in README.md (in your Flowsaic folder); it lists the exact steps."
    exit 1
}
function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}
function Test-Backend {
    try {
        $answer = Invoke-WebRequest -UseBasicParsing -Uri ($Url + "health") -TimeoutSec 2
        return ($answer.Content -match '"ok"')
    } catch { return $false }
}
function Test-Frontend {
    try {
        $answer = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 2
        return ($answer.Content -match 'id="root"')
    } catch { return $false }
}
function Test-PortBusy($number) {
    return [bool](Get-NetTCPConnection -LocalPort $number -State Listen -ErrorAction SilentlyContinue)
}
# Node is installed in Program Files by winget/the installer; a window opened before the
# install doesn't have it on PATH yet.
function Find-Npm {
    $nodeDir = Join-Path $env:ProgramFiles "nodejs"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $nodeDir "npm.cmd"))) {
        $env:Path = "$nodeDir;$env:Path"
    }
    return [bool](Get-Command npm -ErrorAction SilentlyContinue)
}
# Open the page as soon as it answers (a background job, so the servers can start meanwhile).
function Open-WhenReady($pageUrl, $checkUrl) {
    if ($NoBrowser) { return }
    Start-Job -ArgumentList $pageUrl, $checkUrl -ScriptBlock {
        param($page, $check)
        for ($i = 0; $i -lt 120; $i++) {
            try {
                # The backend first (polling it through the proxy would log errors), then the page.
                Invoke-WebRequest -UseBasicParsing -Uri $check -TimeoutSec 2 | Out-Null
                Invoke-WebRequest -UseBasicParsing -Uri $page -TimeoutSec 2 | Out-Null
                Start-Process $page
                return
            } catch { Start-Sleep -Seconds 1 }
        }
    } | Out-Null
}

$openUrl = if ($BackendOnly) { $Url } else { $FrontendUrl }
$backendUp = Test-Backend
$frontendUp = $BackendOnly -or (Test-Frontend)
if ($backendUp -and $frontendUp) {
    Write-Host "Flowsaic is already running at $openUrl" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $openUrl }
    exit 0
}
if (-not $backendUp -and (Test-PortBusy $Port)) { Stop-Start "Something else is using port $Port. Close it, or run: start.cmd -Port 8001" }
if (-not $frontendUp -and (Test-PortBusy $FrontendPort)) { Stop-Start "Something else is using port $FrontendPort. Close it, or run: start.cmd -FrontendPort 8444" }

if (-not $BackendOnly) {
    if (-not (Find-Npm)) { Stop-Start "Node.js isn't installed (the front end needs it). Run setup.cmd first, or use: start.cmd -BackendOnly" }
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) { Stop-Start "The front end isn't installed yet. Run setup.cmd first." }
}

# --- the backend -------------------------------------------------------------------------------
if (-not $backendUp) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Stop-Start "uv isn't installed. Run setup.cmd first." }
    if (-not (Test-Path (Join-Path $Backend ".venv"))) { Stop-Start "Flowsaic isn't set up yet. Double-click setup.cmd first." }
    if (-not ((Test-Path (Join-Path $Backend ".env")) -or (Test-Path (Join-Path $Repo ".env")))) {
        Stop-Start "There's no .env file in your Flowsaic folder. Copy your .env file next to setup.cmd (in File Explorer turn on View > Show > File name extensions and check it's named exactly .env), then double-click setup.cmd."
    }
    # Docker Desktop installed in this session isn't on PATH yet.
    $dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $dockerBin "docker.exe"))) { $env:Path = "$dockerBin;$env:Path" }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Stop-Start "Docker Desktop isn't installed. Double-click setup.cmd first." }

    if (-not (Test-Docker)) {
        $dockerApp = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerApp) { Write-Host "Starting Docker Desktop..."; Start-Process $dockerApp }
        Write-Host "Waiting for Docker (up to 3 minutes)..."
        $deadline = (Get-Date).AddMinutes(3)
        while (-not (Test-Docker)) {
            if ((Get-Date) -gt $deadline) { Stop-Start "Docker isn't running. Open Docker Desktop and wait until it says 'Engine running'." }
            Start-Sleep -Seconds 3
        }
    }

    # The database container is shared by every copy of the repo on this laptop: reuse it if it exists.
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
    if ($code -ne 0) { Stop-Start "Docker couldn't start the database (see the message above)." }
    $deadline = (Get-Date).AddMinutes(2)
    do {
        $health = ((docker inspect -f "{{.State.Health.Status}}" flowsaic-db) | Out-String).Trim()
        if ($health -eq "healthy") { break }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    if ($health -ne "healthy") { Stop-Start "The database didn't become ready. Check Docker Desktop for the flowsaic-db container." }

    # Bring the tables up to date, so a "git pull" with a new migration just works. It only adds
    # what's missing (never drops data) and takes a second when there's nothing to do.
    Write-Host "Updating the database tables..."
    uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Stop-Start "Updating the database tables failed (alembic upgrade head, see the message above)." }

    # An empty database means setup never finished: say so instead of opening an empty app.
    $loaded = @{}
    foreach ($line in (uv run python ..\db\scripts\status.py 2>$null)) {
        if ($line -match "^(\w+)=(\d+)$") { $loaded[$Matches[1]] = [int]$Matches[2] }
    }
    if (($loaded["sections"] -eq 0) -or ($loaded["students"] -eq 0)) {
        Stop-Start "Flowsaic's data isn't loaded yet (no courses or sign-in users). Double-click setup.cmd and let it finish."
    }
}

# --- the front end -------------------------------------------------------------------------------
# Normally Vite runs in this same window: Ctrl+C or closing the window stops it along with the
# backend, and nothing else sends Ctrl+C here (the backend doesn't auto-reload). With -Dev the
# backend reloads, and a reload's Ctrl+C would reach Vite, so Vite gets its own minimized window.
# It forwards /api/... to the backend on -Port (BACKEND_URL), so the cookie stays on one origin.
$vite = $null
if (-not $frontendUp) {
    $env:BACKEND_URL = "http://127.0.0.1:$Port"
    $env:PORT = "$FrontendPort"
    $env:VITE_CONFIG_NATIVE_IGNORE_WARNING = "true"
    if ($Dev) {
        $vite = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "title Flowsaic website (Vite) && npm run dev" -WorkingDirectory $Frontend -WindowStyle Minimized -PassThru
    } else {
        $vite = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory $Frontend -NoNewWindow -PassThru
    }
}
Open-WhenReady $openUrl ($Url + "health")

Write-Host ""
Write-Host "Flowsaic is starting at $openUrl (your browser opens when it's ready)." -ForegroundColor Green
Write-Host "Sign in as 1-5 (any password). Keep this window open; Ctrl+C stops Flowsaic."
if (-not $BackendOnly) { Write-Host "Backend API: $Url  (docs at ${Url}docs, test page at $Url)" }
Write-Host ""
try {
    if ($backendUp) {
        Write-Host "The backend was already running at $Url; only the front end runs in this window."
        if ($vite) { $vite.WaitForExit() }
    } else {
        if ($Dev) {
            Write-Host "Dev mode: the backend reloads when you save a .py file (don't save during a mySAU connect)." -ForegroundColor Yellow
            uv run fastapi dev app/main.py --host 127.0.0.1 --port $Port
        } else {
            # No auto-reload: nothing restarts the backend under a running mySAU connect or the website.
            # 127.0.0.1 keeps it on this laptop only (fastapi run would otherwise listen on the network).
            uv run fastapi run app/main.py --host 127.0.0.1 --port $Port
        }
    }
} finally {
    # Vite usually stops with Ctrl+C too (in -Dev it has its own window); make sure it doesn't outlive this one.
    if ($vite -and -not $vite.HasExited) { cmd /c "taskkill /PID $($vite.Id) /T /F >nul 2>&1" }
}
