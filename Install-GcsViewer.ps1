<#
    Install-GcsViewer.ps1
    -----------------------------------------------------------------------
    Sets up the GCS Viewer on this machine. The viewer (GCSViewer.exe) is a
    fully standalone program - no Python or other software is required.

    This script just registers a "GCS Viewer" app so .gcs / .gem files can
    be opened with it.

    Run from the folder you extracted the zip into:
        powershell -ExecutionPolicy Bypass -File .\Install-GcsViewer.ps1
#>
$ErrorActionPreference = "Stop"
$here     = $PSScriptRoot
$launcher = Join-Path $here "GCSViewer.exe"
$progId   = "GcsViewer.Stone"        # our document type
$appKey   = "GCSViewer.exe"          # our "Open with" application

if (-not (Test-Path $launcher)) {
    throw "GCSViewer.exe was not found next to this script ($here)."
}

Write-Host "Registering the GCS Viewer application (per-user)..."
$classes = "HKCU:\Software\Classes"
$cmd = "`"$launcher`" `"%1`""

# Document type (ProgId)
New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
Set-ItemProperty "$classes\$progId"                    "(default)" "Gemcut Studio Stone (Viewer)"
Set-ItemProperty "$classes\$progId\shell\open"         "(default)" "View gem"
Set-ItemProperty "$classes\$progId\shell\open\command" "(default)" $cmd

# Named application that appears in the "Open with" list
New-Item -Path "$classes\Applications\$appKey\shell\open\command" -Force | Out-Null
Set-ItemProperty "$classes\Applications\$appKey"                    "(default)"       "GCS Viewer"
Set-ItemProperty "$classes\Applications\$appKey"                    "FriendlyAppName" "GCS Viewer"
Set-ItemProperty "$classes\Applications\$appKey\shell\open\command" "(default)"       $cmd
New-Item -Path "$classes\Applications\$appKey\SupportedTypes" -Force | Out-Null

# Register for both faceting formats the viewer understands
foreach ($ext in @('.gcs', '.gem')) {
    Set-ItemProperty "$classes\Applications\$appKey\SupportedTypes" $ext ""
    New-Item -Path "$classes\$ext\OpenWithProgids" -Force | Out-Null
    Set-ItemProperty "$classes\$ext" "(default)" $progId
    New-ItemProperty "$classes\$ext\OpenWithProgids" -Name $progId -Value ([byte[]]@()) -PropertyType None -Force | Out-Null
    $owl = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\OpenWithList"
    New-Item -Path $owl -Force | Out-Null
    Set-ItemProperty $owl "a" $appKey
    Set-ItemProperty $owl "MRUList" "a"
}

# Start Menu shortcut - Windows 11's "Open with" list is built from registered apps
$lnk = Join-Path ([Environment]::GetFolderPath('Programs')) "GCS Viewer.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = $launcher
$sc.WorkingDirectory = Split-Path $launcher
$sc.Description = "GCS Viewer - view Gemcut Studio gem files"
$sc.Save()

# Refresh Explorer's association cache
$sig = '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int id, int flags, IntPtr a, IntPtr b);'
(Add-Type -MemberDefinition $sig -Name Shell -Namespace Win32 -PassThru)::SHChangeNotify(0x08000000,0,[IntPtr]::Zero,[IntPtr]::Zero)

Write-Host ""
Write-Host "Done. To finish (one time), set the default for .gcs AND .gem:" -ForegroundColor Green
Write-Host "  Right-click a .gcs (and a .gem) file > Open with > Choose another app."
Write-Host "  Pick 'GCS Viewer'. If it isn't listed, scroll down and click"
Write-Host "  'Choose an app on your PC' (older Windows: 'More apps' >"
Write-Host "  'Look for another app on this PC'), then browse to:"
Write-Host "      $launcher"
Write-Host "  Tick 'Always use this app', click OK."
Write-Host ""
Write-Host "After that, double-clicking a .gcs or .gem opens the viewer."
