<#
    test_installer.ps1 - run the installer for real and check what it writes.

    powershell -ExecutionPolicy Bypass -File scripts\test_installer.ps1

    test_gcs_viewer.py checks the installer by reading it, which proves a line
    exists and nothing about what Windows ends up with.  This runs it.

    Everything is renamed to sandbox values first - a throwaway ProgId,
    extension, application key, registered-application name and Start Menu
    shortcut - so no real association is touched.  The missing default verb
    that broke double-click for five releases would fail the first check
    below, from the registry rather than from a regex.

    Exit code 0 = all checks passed.
#>
$ErrorActionPreference = "Stop"

$HERE   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$progId = "GcsViewerSelfTest.Stone"
$appKey = "GCSViewerSelfTest.exe"
$ext    = ".gcsselftest"
$appName = "GCS Viewer Self Test"
$capRoot = "GCSViewerSelfTest"

$pass = 0
$fail = @()
function Check($name, $cond, $detail = "") {
    if ($cond) { $script:pass++; Write-Host "  ok   $name" }
    else { $script:fail += $name; Write-Host "  FAIL $name   $detail" }
}

$tmp = Join-Path $env:TEMP ("gcsv-installer-test-" + [Guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Force $tmp | Out-Null
$classes = "HKCU:\Software\Classes"

try {
    # a stand-in for the program: the installer refuses to run without one
    # beside it, and nothing here ever launches it
    Set-Content -Path (Join-Path $tmp $appKey) -Value "not a real program" -Encoding ascii

    foreach ($script in @("Install-GcsViewer.ps1", "Uninstall-GcsViewer.ps1")) {
        $text = Get-Content (Join-Path $HERE $script) -Raw
        $text = $text.Replace('"GcsViewer.Stone"', "`"$progId`"")
        $text = $text.Replace('"GCSViewer.exe"',   "`"$appKey`"")
        $text = $text.Replace("@('.gcs', '.gem')", "@('$ext')")
        $text = $text.Replace('"GCS Viewer.lnk"',  "`"$appName.lnk`"")
        $text = $text.Replace('"GCS Viewer"',      "`"$appName`"")
        $text = $text.Replace('HKCU:\Software\GCSViewer', "HKCU:\Software\$capRoot")
        $text = $text.Replace('Software\GCSViewer\Capabilities', "Software\$capRoot\Capabilities")
        Set-Content -Path (Join-Path $tmp $script) -Value $text -Encoding utf8
    }

    & powershell -ExecutionPolicy Bypass -File (Join-Path $tmp "Install-GcsViewer.ps1") *> $null
    Check "installer exits 0" ($LASTEXITCODE -eq 0) "exit $LASTEXITCODE"

    # THE defect: a document type with no default verb resolves, shows its
    # icon, and has no action for a double-click to invoke
    $verb = (Get-ItemProperty "$classes\$progId" -Name "(default)" -EA SilentlyContinue)."(default)"
    $shellVerb = (Get-ItemProperty "$classes\$progId\shell" -Name "(default)" -EA SilentlyContinue)."(default)"
    Check "the ProgId's shell key names a default verb" ($shellVerb -eq "open") "got '$shellVerb'"

    $cmd = (Get-ItemProperty "$classes\$progId\shell\open\command" -Name "(default)" -EA SilentlyContinue)."(default)"
    Check "the open command points at the program beside the installer" `
        ($cmd -like "*$appKey*" -and $cmd -like '*"%1"*') "got '$cmd'"
    Check "the verb the shell key names actually exists" `
        (Test-Path "$classes\$progId\shell\open") "no shell\open key"

    $icon = (Get-ItemProperty "$classes\$progId\DefaultIcon" -Name "(default)" -EA SilentlyContinue)."(default)"
    Check "documents get an icon" ($icon -like "*$appKey*,0") "got '$icon'"
    Check "the ProgId has a description" (-not [string]::IsNullOrWhiteSpace($verb)) "empty"

    # this subkey made the document type claim to be an application, which
    # listed the program twice and stopped Explorer honouring it
    Check "the ProgId is NOT declared to be an application" `
        (-not (Test-Path "$classes\$progId\Application")) "Application subkey present"

    $extDefault = (Get-ItemProperty "$classes\$ext" -Name "(default)" -EA SilentlyContinue)."(default)"
    Check "the extension points at the ProgId" ($extDefault -eq $progId) "got '$extDefault'"
    Check "the extension lists the ProgId under OpenWithProgids" `
        ((Get-Item "$classes\$ext\OpenWithProgids" -EA SilentlyContinue).GetValueNames() -contains $progId) "absent"

    $appCmd = (Get-ItemProperty "$classes\Applications\$appKey\shell\open\command" -Name "(default)" -EA SilentlyContinue)."(default)"
    Check "the Applications entry has its own open command" ($appCmd -like "*$appKey*") "got '$appCmd'"
    $friendly = (Get-ItemProperty "$classes\Applications\$appKey" -Name "FriendlyAppName" -EA SilentlyContinue).FriendlyAppName
    Check "the Applications entry has a friendly name" ($friendly -eq $appName) "got '$friendly'"
    Check "the Applications entry declares the extension supported" `
        ((Get-Item "$classes\Applications\$appKey\SupportedTypes" -EA SilentlyContinue).GetValueNames() -contains $ext) "absent"

    $cap = "HKCU:\Software\$capRoot\Capabilities"
    Check "a Capabilities key is registered" (Test-Path $cap) "absent"
    Check "Capabilities maps the extension to the ProgId" `
        ((Get-ItemProperty "$cap\FileAssociations" -Name $ext -EA SilentlyContinue).$ext -eq $progId) "absent"
    Check "the app is in RegisteredApplications" `
        ($null -ne (Get-ItemProperty "HKCU:\Software\RegisteredApplications" -Name $appName -EA SilentlyContinue)) "absent"

    $lnk = Join-Path ([Environment]::GetFolderPath('Programs')) "$appName.lnk"
    Check "a Start Menu shortcut is created" (Test-Path $lnk) "absent"
    if (Test-Path $lnk) {
        $target = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath
        Check "the shortcut targets the program, not a folder" ($target -like "*$appKey") "got '$target'"
    }

    # --- and the uninstaller must undo all of it ---
    & powershell -ExecutionPolicy Bypass -File (Join-Path $tmp "Uninstall-GcsViewer.ps1") *> $null
    Check "uninstaller removes the ProgId"            (-not (Test-Path "$classes\$progId"))
    Check "uninstaller removes the Applications entry" (-not (Test-Path "$classes\Applications\$appKey"))
    Check "uninstaller removes the Capabilities key"   (-not (Test-Path "HKCU:\Software\$capRoot"))
    Check "uninstaller removes the Start Menu shortcut" (-not (Test-Path $lnk))
    Check "uninstaller removes the extension key"      (-not (Test-Path "$classes\$ext"))
}
finally {
    # belt and braces: leave nothing behind even if a check threw
    foreach ($k in @("$classes\$progId", "$classes\Applications\$appKey", "$classes\$ext",
                     "HKCU:\Software\$capRoot")) {
        Remove-Item $k -Recurse -Force -ErrorAction SilentlyContinue
    }
    Remove-ItemProperty "HKCU:\Software\RegisteredApplications" -Name $appName -ErrorAction SilentlyContinue
    Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) "$appName.lnk") -Force -ErrorAction SilentlyContinue
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "$pass checks passed, $($fail.Count) failed"
foreach ($f in $fail) { Write-Host "  FAILED: $f" }
if ($fail.Count) { exit 1 } else { exit 0 }
