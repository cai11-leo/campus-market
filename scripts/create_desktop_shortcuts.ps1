# Create Campus Market shortcuts on the current user's Desktop.
# Run: powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcuts.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$LocalBatch = Join-Path $ProjectRoot "启动校园集市.bat"
$PhoneBatch = Join-Path $ProjectRoot "手机打开.bat"
$Python = (Get-Command python).Source
$Wsh = New-Object -ComObject WScript.Shell

if (-not (Test-Path $LocalBatch)) { throw "Local launcher not found: $LocalBatch" }
if (-not (Test-Path $PhoneBatch)) { throw "Phone launcher not found: $PhoneBatch" }

$LocalPath = Join-Path $Desktop "校园集市.lnk"
$Local = $Wsh.CreateShortcut($LocalPath)
$Local.TargetPath = $LocalBatch
$Local.WorkingDirectory = $ProjectRoot
$Local.IconLocation = "$Python,0"
$Local.Hotkey = "CTRL+ALT+C"
$Local.Description = "在本机启动校园集市并打开浏览器"
$Local.WindowStyle = 1
$Local.Save()

$PhonePath = Join-Path $Desktop "校园集市-手机同WiFi.lnk"
$Phone = $Wsh.CreateShortcut($PhonePath)
$Phone.TargetPath = $PhoneBatch
$Phone.WorkingDirectory = $ProjectRoot
$Phone.IconLocation = "$Python,0"
$Phone.Hotkey = "CTRL+ALT+M"
$Phone.Description = "启动手机同 Wi-Fi 访问地址"
$Phone.WindowStyle = 1
$Phone.Save()

$FolderPath = Join-Path $Desktop "校园集市-项目文件夹.lnk"
$Folder = $Wsh.CreateShortcut($FolderPath)
$Folder.TargetPath = $ProjectRoot
$Folder.IconLocation = "$env:SystemRoot\System32\shell32.dll,3"
$Folder.Description = "打开校园集市项目文件夹"
$Folder.Save()

$OldShare = Join-Path $Desktop "校园集市-公网分享.lnk"
if (Test-Path $OldShare) { Remove-Item $OldShare -Force }

Write-Host "Desktop: $Desktop"
Write-Host "Local shortcut: $LocalPath"
Write-Host "Phone shortcut: $PhonePath"
Write-Host "Folder shortcut: $FolderPath"
Write-Host "Optional public sharing: $(Join-Path $ProjectRoot '分享给别人.bat')"
