$WshShell = New-Object -ComObject WScript.Shell
$DesktopPaths = @(
    [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop),
    "C:\Users\ASUS\Desktop"
) | Select-Object -Unique | Where-Object { Test-Path $_ }

$IconFile = "C:\Users\ASUS\Ultron\ultron-ui\assets\icon.ico"

foreach ($dp in $DesktopPaths) {
    $ShortcutPath = Join-Path $dp "Ultron Assistant.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "C:\Users\ASUS\Ultron\start.bat"
    $Shortcut.WorkingDirectory = "C:\Users\ASUS\Ultron"
    $Shortcut.IconLocation = "$IconFile, 0"
    $Shortcut.Description = "Launch Ultron Desktop AI Voice Assistant"
    $Shortcut.Save()
    Write-Host "[OK] Desktop shortcut updated at: $ShortcutPath" -ForegroundColor Green
}
