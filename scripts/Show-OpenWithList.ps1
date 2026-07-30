<#
    Show-OpenWithList.ps1
    -----------------------------------------------------------------------
    Print exactly what Windows would offer in "Open with" for .gcs and .gem.

        powershell -ExecutionPolicy Bypass -File .\scripts\Show-OpenWithList.ps1

    This asks the shell the same question its own picker asks -
    SHAssocEnumHandlers - so it answers "is GCS Viewer listed?" without
    opening a dialog and squinting at it.

    It exists because of a real failure: the viewer was registered correctly
    as a handler for both extensions and was still absent from the picker,
    leaving "Choose an app on your PC" as the only route to it.  Windows 11
    builds that list from the Default Programs registration -
    RegisteredApplications plus a Capabilities key - which is a *separate*
    thing from registering a handler.  Install-GcsViewer.ps1 writes both now,
    and this is how you check it took.

    Read-only.  It enumerates; it never sets a default.  Windows does not
    allow that to be automated - see the note in INSTALL.md.
#>

$src = @'
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("F04061AC-1659-4a3f-A954-775AA57FC083"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAssocHandler {
    [PreserveSig] int GetName([MarshalAs(UnmanagedType.LPWStr)] out string ppsz);
    [PreserveSig] int GetUIName([MarshalAs(UnmanagedType.LPWStr)] out string ppsz);
    [PreserveSig] int GetIconLocation([MarshalAs(UnmanagedType.LPWStr)] out string ppszPath,
                                      out int pIndex);
    [PreserveSig] int IsRecommended();
    [PreserveSig] int MakeDefault([MarshalAs(UnmanagedType.LPWStr)] string pszDescription);
    [PreserveSig] int Invoke(IntPtr pdo);
    [PreserveSig] int CreateInvoker(IntPtr pdo, out IntPtr ppInvoker);
}

[ComImport, Guid("973810ae-9599-4b88-9e4d-6ee98c9552da"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IEnumAssocHandlers {
    [PreserveSig] int Next(uint celt,
        [Out, MarshalAs(UnmanagedType.LPArray, SizeParamIndex = 0)] IAssocHandler[] rgelt,
        out uint pceltFetched);
}

public static class AssocList {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHAssocEnumHandlers([MarshalAs(UnmanagedType.LPWStr)] string pszExtra,
        int afFilter, out IEnumAssocHandlers ppEnumHandler);

    public static string[] For(string ext) {
        IEnumAssocHandlers e;
        SHAssocEnumHandlers(ext, 0, out e);
        var outp = new System.Collections.Generic.List<string>();
        var one = new IAssocHandler[1];
        uint got;
        while (e.Next(1, one, out got) == 0 && got == 1) {
            string name, ui;
            one[0].GetName(out name);
            one[0].GetUIName(out ui);
            // IsRecommended returns S_OK for the apps shown under "Suggested"
            string tag = one[0].IsRecommended() == 0 ? "[suggested]" : "[other]    ";
            outp.Add(tag + " " + ui + "   ->   " + name);
            Marshal.ReleaseComObject(one[0]);
        }
        return outp.ToArray();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$missing = $false
foreach ($ext in @('.gcs', '.gem')) {
    Write-Host ""
    Write-Host "=== what Open with would list for $ext ===" -ForegroundColor Cyan
    $list = [AssocList]::For($ext)
    $list | ForEach-Object { "  $_" }
    if ($list | Where-Object { $_ -match 'GCS Viewer' }) {
        Write-Host "  GCS Viewer is listed." -ForegroundColor Green
    } else {
        Write-Host "  GCS Viewer is NOT listed - run Install-GcsViewer.ps1 from the" -ForegroundColor Red
        Write-Host "  folder that holds GCSViewer.exe, then try again." -ForegroundColor Red
        $missing = $true
    }
}

Write-Host ""
foreach ($ext in @('.gcs', '.gem')) {
    $k = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\UserChoice"
    $p = (Get-ItemProperty $k -Name ProgId -ErrorAction SilentlyContinue).ProgId
    if ($p) { "current default for $ext : $p" }
    else     { "current default for $ext : not set - pick it once, see INSTALL.md" }
}

# --- will a double-click actually run anything? --------------------------
#
# Everything above answers "is the viewer offered?".  That is not the same
# question as "does double-click work", and the difference cost an evening:
# the viewer was listed, the command was right, Settings showed it as the
# default, and Explorer prompted anyway - because the ProgId's `shell` key had
# no default value naming which verb to invoke.  Nothing above would have
# caught it.  This walks the chain the shell walks and says where it breaks.
Write-Host ""
Write-Host "=== will a double-click run anything? ===" -ForegroundColor Cyan
$broken = $false
foreach ($ext in @('.gcs', '.gem')) {
    $uc = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\UserChoice" `
           -Name ProgId -ErrorAction SilentlyContinue).ProgId
    $cls = (Get-ItemProperty "HKCU:\Software\Classes\$ext" -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if (-not $cls) {
        $cls = (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\$ext" -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    }
    $progId = if ($uc) { $uc } else { $cls }
    $via    = if ($uc) { "your saved choice" } else { "the class default" }

    if (-not $progId) {
        Write-Host "  $ext : nothing claims this extension" -ForegroundColor Red
        $broken = $true; continue
    }

    # an Applications\<exe> ProgId lives under Classes directly, same as ours
    $root = "Registry::HKEY_CLASSES_ROOT\$progId"
    $verb = (Get-ItemProperty "$root\shell" -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if (-not $verb) {
        # no named verb: the shell falls back to "open" only if it exists
        if (Test-Path "$root\shell\open\command") {
            Write-Host "  $ext -> $progId ($via)" -ForegroundColor Yellow
            Write-Host "        shell key names NO default verb." -ForegroundColor Red
            Write-Host "        Explorer will show the picker and picking the app will do" -ForegroundColor Red
            Write-Host "        nothing.  Re-run Install-GcsViewer.ps1 - it writes it." -ForegroundColor Red
            $broken = $true
        } else {
            Write-Host "  $ext -> $progId ($via): no verbs at all" -ForegroundColor Red
            $broken = $true
        }
        continue
    }

    $cmdKey = "$root\shell\$verb\command"
    $cmd = (Get-ItemProperty $cmdKey -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if (-not $cmd) {
        Write-Host "  $ext -> $progId ($via): default verb is '$verb', which has no command" -ForegroundColor Red
        $broken = $true; continue
    }
    $exe = if ($cmd -match '"([^"]+)"') { $matches[1] } else { ($cmd -split ' ')[0] }
    if (-not (Test-Path -LiteralPath $exe)) {
        Write-Host "  $ext -> $progId ($via): '$verb' runs $exe, which is missing" -ForegroundColor Red
        $broken = $true; continue
    }
    Write-Host "  $ext -> $progId ($via), verb '$verb' -> $exe" -ForegroundColor Green
}
if (-not $broken) { Write-Host "  both extensions have a default action that resolves to a real program." }

# --- stale entries -------------------------------------------------------
#
# An app that has been uninstalled, renamed or moved leaves entries behind
# that keep it in the Open-with list pointing at a file that is no longer
# there.  They hide in more places than is obvious: an auto-generated
# <ext>_auto_file ProgId, that ProgId listed under the extension's
# OpenWithProgids, a friendly name in MuiCache, and - the one that outlives
# an explorer.exe restart and a registry sweep of the obvious subtrees -
# ApplicationAssociationToasts.  Finding one of those took four searches by
# hand; this finds all four at once.
#
# Reported, never deleted.  These are the user's associations, not ours.
Write-Host ""
Write-Host "=== stale entries (targets that no longer exist) ===" -ForegroundColor Cyan
$stale = @()

foreach ($ext in @('.gcs', '.gem')) {
    $auto = "HKCU:\Software\Classes\$($ext.TrimStart('.'))_auto_file\shell\open\command"
    $cmd = (Get-ItemProperty $auto -Name '(default)' -ErrorAction SilentlyContinue).'(default)'
    if ($cmd) {
        $exe = if ($cmd -match '"([^"]+)"') { $matches[1] } else { ($cmd -split ' ')[0] }
        if (-not (Test-Path $exe)) {
            $stale += "reg delete `"HKCU\Software\Classes\$($ext.TrimStart('.'))_auto_file`" /f"
            Write-Host "  $ext auto_file ProgId -> $exe  (missing)"
        }
    }
    $owp = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\OpenWithProgids"
    foreach ($n in (Get-Item $owp -ErrorAction SilentlyContinue).Property) {
        if ($n -like '*_auto_file' -and -not (Test-Path "HKCU:\Software\Classes\$n")) {
            $stale += "reg delete `"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\OpenWithProgids`" /v `"$n`" /f"
            Write-Host "  $ext OpenWithProgids -> $n  (ProgId gone)"
        }
    }
}

# MuiCache keeps app display names keyed by executable *path*, so a program
# that has been moved leaves a name pointing at a file that is gone - which
# surfaces as a second, dead row in the picker.  This was the fifth hiding
# place, found only after the other four had been cleared and the ghost was
# still there.
# Scoped to this program deliberately.  Unscoped, this finds every app the
# machine has ever uninstalled - 475 rows on the machine it was written on -
# and printing a `reg delete` for each would invite clearing other programs'
# entries to fix ours.  Only names for a viewer executable are our business.
$muiKey = "HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
foreach ($n in (Get-Item $muiKey -ErrorAction SilentlyContinue).Property) {
    if ($n -notmatch 'GCSViewer|gcs_viewer') { continue }
    if ($n -match '^(.+?)\.(FriendlyAppName|ApplicationCompany|ApplicationDescription)$') {
        $target = $matches[1]
        if ($target -match '^[A-Za-z]:\\' -and -not (Test-Path -LiteralPath $target)) {
            $stale += "reg delete `"HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache`" /v `"$n`" /f"
            Write-Host "  shell display name -> $target  (missing)"
        }
    }
}

$toastKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts"
foreach ($n in (Get-Item $toastKey -ErrorAction SilentlyContinue).Property) {
    if ($n -match '^Applications\\(.+?)_(\.[A-Za-z0-9]+)$') {
        $app = $matches[1]
        if (-not (Get-Item "HKCU:\Software\Classes\Applications\$app" -ErrorAction SilentlyContinue) -and
            -not (Get-Item "HKLM:\SOFTWARE\Classes\Applications\$app" -ErrorAction SilentlyContinue)) {
            $stale += "reg delete `"HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts`" /v `"$n`" /f"
            Write-Host "  association toast -> $n  (no such application registered)"
        }
    }
}

if (-not $stale) {
    Write-Host "  none"
} else {
    Write-Host ""
    Write-Host "  To clear them, run these - they are your associations, so this" -ForegroundColor Yellow
    Write-Host "  script prints them rather than running them:" -ForegroundColor Yellow
    $stale | Sort-Object -Unique | ForEach-Object { "    $_" }
    Write-Host "  Then restart explorer.exe: the Open-with menu is cached."
}

if ($missing) { exit 1 }
