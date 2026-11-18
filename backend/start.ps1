<#
  Start the Flowsaic backend on Windows. Double-click start.cmd in the Flowsaic folder.
  Starts Docker and the database if needed, runs the server and opens the sign-in page.
  Stop the server with Ctrl+C (or close the window).
  If Flowsaic is already running, it just opens the page instead of starting a second copy.

  Optional: -Port 8001 (another port), -NoBrowser (don't open the browser).
#>
param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)
$ErrorActionPreference = "Continue"
$Url = "http://127.0.0.1:$Port/"
$Backend = $PSScriptRoot
$Repo = Split-Path $Backend -Parent
Set-Location $Backend

function Stop-Start($text) {
    Write-Host ""
    Write-Host "COULDN'T START: $text" -ForegroundColor Red
    exit 1
}
function Test-Docker {
    cmd /c "docker info >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Test-Running {
    try {
        $answer = Invoke-WebRequest -UseBasicParsing -Uri ($Url + "health") -TimeoutSec 2
        return ($answer.Content -match '"ok"')
    } catch { return $false }
}

if (Test-Running) {
    Write-Host "Flowsaic is already running at $Url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) { Stop-Start "Something else is using port $Port. Close it, or run: start.cmd -Port 8001" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Stop-Start "uv isn't installed. Run setup.cmd first." }
if (-not (Test-Path (Join-Path $Backend ".venv"))) { Stop-Start "Flowsaic isn't set up yet. Run setup.cmd first." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Stop-Start "Docker Desktop isn't installed. Run setup.cmd first." }

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

Push-Location $Repo
docker compose up -d
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Stop-Start "Docker couldn't start the database (see the message above)." }
$deadline = (Get-Date).AddMinutes(2)
do {
    $health = ((docker inspect -f "{{.State.Health.Status}}" flowsaic-db) | Out-String).Trim()
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($health -ne "healthy") { Stop-Start "The database didn't become ready. Check Docker Desktop for the flowsaic-db container." }

# Open the sign-in page as soon as the server answers.
if (-not $NoBrowser) {
    Start-Job -ArgumentList $Url -ScriptBlock {
        param($url)
        for ($i = 0; $i -lt 90; $i++) {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri ($url + "health") -TimeoutSec 2 | Out-Null
                Start-Process $url
                return
            } catch { Start-Sleep -Seconds 1 }
        }
    } | Out-Null
}

Write-Host ""
Write-Host "Flowsaic is starting at $Url (your browser opens when it's ready)." -ForegroundColor Green
Write-Host "Sign in as 1, 2, 3 or 4 (any password). Keep this window open; Ctrl+C stops the server."
Write-Host ""
uv run fastapi dev app/main.py --port $Port
