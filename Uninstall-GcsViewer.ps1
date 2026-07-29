<#
    Uninstall-GcsViewer.ps1
    Removes the per-user GCS Viewer file association and application entry.
    (The viewer itself is just GCSViewer.exe - delete its folder to remove it.)

    Note: if you set GCS Viewer as the *default* via "Open with > Always",
    Windows stores a protected UserChoice that this script cannot delete.
    To clear it: Settings > Apps > Default apps > search ".gcs" and change it,
    or just pick a different app via "Open with > Choose another app".
#>
$ErrorActionPreference = "SilentlyContinue"
$classes = "HKCU:\Software\Classes"
$progId  = "GcsViewer.Stone"
$appKey  = "GCSViewer.exe"

Remove-Item "$classes\$progId" -Recurse -Force
Remove-Item "$classes\Applications\$appKey" -Recurse -Force
# the Default Programs registration that puts it in the Open-with dialog and
# in Settings > Default apps
Remove-ItemProperty "HKCU:\Software\RegisteredApplications" -Name "GCS Viewer"
Remove-Item "HKCU:\Software\GCSViewer" -Recurse -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) "GCS Viewer.lnk") -Force

foreach ($ext in @('.gcs', '.gem')) {
    Remove-ItemProperty "$classes\$ext\OpenWithProgids" -Name $progId
    Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\OpenWithList" -Recurse -Force
    # Only clear the extension default if it still points at us
    if ((Get-ItemProperty "$classes\$ext")."(default)" -eq $progId) {
        Remove-Item "$classes\$ext" -Recurse -Force
    }
}

$sig = '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int id, int flags, IntPtr a, IntPtr b);'
(Add-Type -MemberDefinition $sig -Name Shell2 -Namespace Win32 -PassThru)::SHChangeNotify(0x08000000,0,[IntPtr]::Zero,[IntPtr]::Zero)

Write-Host "Removed the GCS Viewer application and file association."
Write-Host "If you'd set it as the default, also change it in Settings > Default apps (.gcs)."
