param (
    [switch]$Silent = $false,
    [switch]$Console = $false,
    [switch]$Stop = $false
)

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "ultron-backend"
$UiDir = Join-Path $RootDir "ultron-ui"
$PythonExe = Join-Path $RootDir "venv\Scripts\python.exe"
$ElectronCmd = Join-Path $UiDir "node_modules\.bin\electron.cmd"

if ($Stop) {
    Write-Host "[*] Stopping Ultron processes..." -ForegroundColor Yellow
    Get-Process -Name "python", "pythonw", "electron" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*Ultron*" } | Stop-Process -Force
    Write-Host "[OK] Ultron stopped." -ForegroundColor Green
    exit
}

if (-not $Silent) {
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "            ULTRON DESKTOP AI ASSISTANT            " -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan
}

$backendWindowStyle = if ($Console) { "Normal" } else { "Hidden" }


# 1. Start Python Backend
$serverScript = Join-Path $BackendDir "server.py"
$targetExe = if ($Console) { $PythonExe } else { Join-Path $RootDir "venv\Scripts\pythonw.exe" }
Start-Process -FilePath $targetExe -ArgumentList "`"$serverScript`"" -WorkingDirectory $BackendDir -WindowStyle $backendWindowStyle

# Wait for backend WebSocket to bind (up to 6s)
$retries = 12
while ($retries -gt 0) {
    $conn = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
    if ($conn) { break }
    Start-Sleep -Milliseconds 500
    $retries--
}

# 2. Start Electron UI
Start-Process -FilePath $ElectronCmd -ArgumentList "." -WorkingDirectory $UiDir

if (-not $Silent) {
    Write-Host "[OK] Ultron background service and overlay started." -ForegroundColor Green
    Write-Host "[*] Listening for 'Hey Ultron'..." -ForegroundColor Cyan
}
