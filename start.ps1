# Sets up on first run, starts the Thatha TV web server in the background,
# then locks the PC into the full-screen remote. Use -NoKiosk to only start the server.
param([switch]$NoKiosk)
Set-Location $PSScriptRoot
$url = "http://127.0.0.1:8000"

# Run from the desktop icon the window closes on exit, so keep errors on screen until Enter
function Fail($msg) { Write-Host $msg -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

# Get the latest version from GitHub. Never blocks starting: no internet just means the current version runs.
if ((Test-Path .git) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Checking for updates..."
    $env:GIT_TERMINAL_PROMPT = "0"
    git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=15 pull --ff-only -q 2>&1 | Out-Null
}

if (-not (Test-Path .venv\Scripts\python.exe)) {
    # Python is often installed but not on PATH (and "python" may be the Microsoft Store stub)
    $python = @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                              "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
                Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName) +
              @(Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } |
                Select-Object -ExpandProperty Source) | Select-Object -First 1
    if (-not $python) {
        Fail "Python is not installed. Install Python 3.11+ from python.org, then try again."
    }
    & $python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Recurse -Force .venv
        Fail "Installing packages failed - check the internet connection and try again."
    }
}
if (-not (Test-Path .lgtv_client_key)) {
    Write-Host "No TV key found - pairing now. Turn the TV on and accept the prompt on the TV."
    .\.venv\Scripts\python pair.py
    if (-not (Test-Path .lgtv_client_key)) { Fail "Pairing failed. Make sure the TV is on, then try again." }
}
if (-not (Test-Path .unlock_pin)) {
    do { $pin = Read-Host "Choose a PIN (4-12 digits) to unlock the PC from the remote screen" }
    until ($pin -match '^\d{4,12}$')
    Set-Content .unlock_pin $pin
}

# Install new packages if an update changed requirements.txt
$reqs = (Get-FileHash requirements.txt).Hash
if ((Get-Content .venv\requirements.hash -ErrorAction SilentlyContinue) -ne $reqs) {
    .\.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -eq 0) { Set-Content .venv\requirements.hash $reqs }
}

function ServerUp {
    try { Invoke-RestMethod "$url/status" -TimeoutSec 2 | Out-Null; $true } catch { $false }
}

# If the running server (and kiosk) are from older code, stop them so the new version starts below
$version = (Get-FileHash server.py, live_tv.py, kiosk.ps1, static\index.html | ForEach-Object Hash) -join ""
if ((ServerUp) -and (Get-Content .server-version -ErrorAction SilentlyContinue) -ne $version) {
    Write-Host "Restarting with the new version..."
    $old = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object OwningProcess) +
           @(Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'msedge.exe'" |
             Where-Object { $_.CommandLine -like "*$PSScriptRoot\kiosk.ps1*" -or $_.CommandLine -like "*$PSScriptRoot\.kiosk-profile*" } |
             ForEach-Object ProcessId)
    $old | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    for ($i = 0; $i -lt 10 -and (ServerUp); $i++) { Start-Sleep 1 }
}
if (-not (ServerUp)) {
    Set-Content .server-version $version
    Start-Process .\.venv\Scripts\python.exe -ArgumentList "server.py" -WindowStyle Hidden `
        -RedirectStandardOutput server.log -RedirectStandardError server.err.log
    for ($i = 0; $i -lt 30 -and -not (ServerUp); $i++) { Start-Sleep 1 }
    if (-not (ServerUp)) { Fail "Server did not start - see server.err.log" }
}

Write-Host "Server running at $url"

# Turn the TV on (in the background, so the remote appears straight away)
Start-Process .\.venv\Scripts\python.exe -ArgumentList "live_tv.py on" -WindowStyle Hidden

if (-not $NoKiosk) {
    Invoke-RestMethod "$url/kiosk/lock" -Method Post | Out-Null
    Start-Process powershell -WindowStyle Hidden `
        -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSScriptRoot\kiosk.ps1`""
}
