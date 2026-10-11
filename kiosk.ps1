# Keeps Edge full-screen on the remote until the PIN is entered on screen.
# Started hidden by start.ps1, so there is no window to close.
Set-Location $PSScriptRoot

# Only one copy, so double-clicking the desktop icon doesn't start two watchers
$single = New-Object System.Threading.Mutex($false, "ThathaTvKiosk")
if (-not $single.WaitOne(0)) { exit }

$url = "http://127.0.0.1:8000"
$profileDir = Join-Path $PSScriptRoot ".kiosk-profile"   # own profile, so it's a separate Edge we can track
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
$edgeArgs = @("--kiosk", "$url/?kiosk", "--edge-kiosk-type=fullscreen", "--no-first-run",
              "--user-data-dir=`"$profileDir`"")
$shell = New-Object -ComObject WScript.Shell

# Keep the PC awake with the screen on while the remote is showing, so Windows never
# sleeps or locks the screen (the iPad needs the PC awake too). Cleared when this script exits.
Add-Type -Name Power -Namespace Win32 -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][Win32.Power]::SetThreadExecutionState(0x80000003)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED

# Main Edge process using the kiosk profile (child processes have --type=)
function KioskBrowser {
    Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" |
        Where-Object { $_.CommandLine -like "*$profileDir*" -and $_.CommandLine -notlike "*--type=*" } |
        Select-Object -First 1
}

# Server down for 10s counts as unlocked, so a crash never traps the PC on an error page
$failures = 0
function Locked {
    try { $locked = (Invoke-RestMethod "$url/kiosk" -TimeoutSec 3).locked; $script:failures = 0; return $locked }
    catch { $script:failures++; return $script:failures -lt 10 }
}

while (Locked) {
    $browser = KioskBrowser
    if (-not $browser) {
        Start-Process $edge -ArgumentList $edgeArgs     # closed (e.g. Alt+F4): bring it straight back
        Start-Sleep 3
    } else {
        [void]$shell.AppActivate([int]$browser.ProcessId)  # pull it in front of anything opened on top
    }
    Start-Sleep 1
}

Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" |
    Where-Object { $_.CommandLine -like "*$profileDir*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
