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
Set-ItemProperty "$classes\$progId\shell\open\command" "(default)" $cmd
# Name the default verb.  Without this the "shell" key has no default value,
# so nothing declares which verb a double-click should invoke - the file type
# resolves, the icon appears, and there is no default action to run.  Every
# working document type on this machine sets it; ours had not.
Set-ItemProperty "$classes\$progId\shell"              "(default)" "open"

# Icon for .gcs / .gem documents in Explorer - index 0 is the icon compiled
# into the exe, so there is no separate .ico file to keep alongside it
New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
Set-ItemProperty "$classes\$progId\DefaultIcon"        "(default)" "`"$launcher`",0"

# REPAIR: versions 1.0.19 to 1.0.25 also wrote an "Application" subkey here,
# on the theory that it was needed to appear in Settings > Default apps.  It
# was not - and it appears to have cost more than it bought.  A ProgId with an
# Application subkey declares itself an *application* rather than a document
# type, which showed up two ways: the program was listed twice in the
# open-with dialog (once as this ProgId, once as the real Applications\<exe>
# entry), and Explorer stopped honouring the class association it had been
# honouring for weeks, prompting on every double-click instead.  Removed here
# rather than merely not written, so re-running this repairs a machine that
# ran one of those versions.
Remove-Item "$classes\$progId\Application" -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty "$classes\$progId" -Name "FriendlyTypeName" -ErrorAction SilentlyContinue
Remove-ItemProperty "$classes\$progId\shell\open" -Name "(default)" -ErrorAction SilentlyContinue

# REPAIR: the shell remembers app display names per executable *path*, so a
# copy that has been moved leaves an entry naming a file that is gone.  Those
# stale names can surface as a second, dead row in the open-with dialog.
$mui = "$classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
if (Test-Path $mui) {
    $props = (Get-Item $mui).GetValueNames() | Where-Object { $_ -like "*$appKey.*" }
    foreach ($v in $props) {
        $target = $v -replace '\.(FriendlyAppName|ApplicationCompany|ApplicationDescription)$',''
        if ($target -and -not (Test-Path -LiteralPath $target)) {
            Remove-ItemProperty $mui -Name $v -ErrorAction SilentlyContinue
            Write-Host "  cleared a stale shell entry for $target"
        }
    }
}

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

# RegisteredApplications/Capabilities: REMOVED 2026-08-03.  A per-user
# Capabilities registration creates a SECOND "GCS Viewer" identity in the
# Windows 11 picker alongside the Applications\<exe> entry - two identical
# rows, and on this machine the pair made the picker unusable (selection
# would not launch, "Just once" grayed, defaults would not stick).  The
# Applications\<exe> entry + OpenWithList above are sufficient for listing;
# the "Choose an app on your PC" browse fallback always works regardless.
# This block now REPAIRS machines that have the old registration.
Remove-ItemProperty "HKCU:\Software\RegisteredApplications" "GCS Viewer" `
    -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\GCSViewer" -Recurse -Force -ErrorAction SilentlyContinue

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
    Write-Host "      picked it, so the default for $($broken -join ' and ') is now stale."
    Write-Host "      Double-clicking one does nothing at all - no error, no prompt."
    Write-Host "      Anything you never explicitly set has followed the move already."
    Write-Host ""
    Write-Host "      Re-picking GCS Viewer will NOT fix it on its own: the saved" -ForegroundColor Yellow
    Write-Host "      choice already names this app, so Windows sees no change and" -ForegroundColor Yellow
    Write-Host "      greys out the Always button.  Break it in two steps:" -ForegroundColor Yellow
    foreach ($ext in $broken) {
        Write-Host "        1. right-click a $ext > Open with > Choose another app >"
        Write-Host "           pick Notepad > Always"
        Write-Host "        2. do it again, picking GCS Viewer > Always"
    }
    Write-Host "      Step 1 replaces the stale entry with a valid one, which makes"
    Write-Host "      step 2 a real change that Windows will accept."
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
