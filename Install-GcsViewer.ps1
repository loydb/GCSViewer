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

# Icon for .gcs / .gem documents in Explorer - index 0 is the icon compiled
# into the exe, so there is no separate .ico file to keep alongside it
New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
Set-ItemProperty "$classes\$progId\DefaultIcon"        "(default)" "`"$launcher`",0"

# Present the ProgId as an *application*, not merely as a document type with
# a handler.  Settings > Apps > Default apps builds its per-extension list
# from ProgIds and names each entry from this subkey; a ProgId without one is
# a file type as far as that page is concerned, and the app never appears in
# it - correctly registered, correctly associated, and unofferable.
New-Item -Path "$classes\$progId\Application" -Force | Out-Null
Set-ItemProperty "$classes\$progId\Application" "ApplicationName"        "GCS Viewer"
Set-ItemProperty "$classes\$progId\Application" "ApplicationIcon"        "`"$launcher`",0"
Set-ItemProperty "$classes\$progId\Application" "ApplicationCompany"     "GCS Viewer"
Set-ItemProperty "$classes\$progId\Application" "ApplicationDescription" `
    "View Gemcut Studio .gcs and GemCad .gem faceting designs."
Set-ItemProperty "$classes\$progId"             "FriendlyTypeName"       "Faceting design"

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

# Registered application (Default Programs).  This is what makes Windows 11
# list "GCS Viewer" at all - in the "Select an app to open this file" dialog
# and in Settings > Apps > Default apps.  Without it the app is reachable
# only through "Choose an app on your PC", browsing to the .exe by hand,
# because that dialog is built from RegisteredApplications rather than from
# the Applications\<exe> entry above.
$capRoot = "HKCU:\Software\GCSViewer"
New-Item -Path "$capRoot\Capabilities\FileAssociations" -Force | Out-Null
Set-ItemProperty "$capRoot\Capabilities" "ApplicationName"        "GCS Viewer"
Set-ItemProperty "$capRoot\Capabilities" "ApplicationDescription" `
    "View Gemcut Studio .gcs and GemCad .gem faceting designs - three shaded views and the cutting instructions."
Set-ItemProperty "$capRoot\Capabilities" "ApplicationIcon"        "`"$launcher`",0"
foreach ($ext in @('.gcs', '.gem')) {
    Set-ItemProperty "$capRoot\Capabilities\FileAssociations" $ext $progId
}
New-Item -Path "HKCU:\Software\RegisteredApplications" -Force | Out-Null
Set-ItemProperty "HKCU:\Software\RegisteredApplications" "GCS Viewer" `
    "Software\GCSViewer\Capabilities"

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

# Did the install move since last time?  Windows validates a saved default
# against the app registration as it stood when the user picked it, so moving
# the program invalidates it - and then a double-click does nothing at all
# rather than falling back or prompting.  An extension with no saved default
# is unaffected: it falls through to the class default, which is rewritten
# above and follows the move.  Remember where we registered, so the next run
# can say which case the user is in instead of leaving them to find out.
$prev = (Get-ItemProperty "$capRoot" -Name "InstallPath" -ErrorAction SilentlyContinue).InstallPath
Set-ItemProperty "$capRoot" "InstallPath" $launcher

$broken = @()
foreach ($ext in @('.gcs', '.gem')) {
    $uc = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\UserChoice"
    $pid_ = (Get-ItemProperty $uc -Name ProgId -ErrorAction SilentlyContinue).ProgId
    if ($pid_ -and $prev -and $prev -ne $launcher -and
        ($pid_ -eq $progId -or $pid_ -eq "Applications\$appKey")) {
        $broken += $ext
    }
}

if ($broken) {
    Write-Host ""
    Write-Host "NOTE: this copy moved since it was last registered:" -ForegroundColor Yellow
    Write-Host "        was  $prev"
    Write-Host "        now  $launcher"
    Write-Host "      Windows ties a saved default to where the program was when you"
    Write-Host "      picked it, so the default for $($broken -join ' and ') is now stale and"
    Write-Host "      double-clicking one will do nothing. Set it again (below) - once."
    Write-Host "      Anything you never explicitly set has followed the move already."
}

Write-Host ""
Write-Host "Registered. Windows does not allow a program to make itself the" -ForegroundColor Green
Write-Host "default for a file type, so finish it by hand - once for .gcs and" -ForegroundColor Green
Write-Host "once for .gem, which Windows tracks separately." -ForegroundColor Green
Write-Host ""
Write-Host "  Settings > Apps > Default apps"
Write-Host "  In 'Set a default for a file type or link type', type   .gcs"
Write-Host "  Click the .gcs row, choose 'GCS Viewer', click 'Set default'."
Write-Host "  Then do the same for   .gem"
Write-Host ""
Write-Host "Or from a file: right-click a .gcs > Open with > Choose another app,"
Write-Host "click 'GCS Viewer', then click 'Always'.  ('Always' only appears once"
Write-Host "an app is selected.)  If GCS Viewer is not listed at all, scroll to"
Write-Host "the bottom and use 'Choose an app on your PC', then browse to:"
Write-Host "      $launcher"
Write-Host ""
Write-Host "After that, double-clicking a .gcs or .gem opens the viewer."
