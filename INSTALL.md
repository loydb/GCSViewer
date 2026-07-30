# GCS Viewer — Installation

A Windows app that shows a faceted gem from a **Gemcut Studio `.gcs`** or
**GemCad `.gem`** file as three shaded views — table, side, and a 3/4 view you
can turn — plus the cutting instructions. After installing, double-clicking a
design opens it.

Nothing else is required: no Python, no libraries, no admin rights.

## Which download

| | Starts in | On disk | Best for |
|---|---|---|---|
| **`GCSViewer.exe`** alone | ~1.5 s | one 30 MB file | a USB stick, emailing, trying it out |
| **`GCSViewer-<version>-windows-folder.zip`** | ~0.4 s | ~70 MB folder | day-to-day use |

The single file unpacks itself into `%TEMP%` on **every** launch, which is
where the extra second goes. The folder build is already unpacked, and is the
one to use where policy stops programs running from `%TEMP%`. It contains an
`_internal` folder of libraries — leave it alone; the viewer will not start
without it.

Both zips also contain `Install-GcsViewer.ps1`, `Uninstall-GcsViewer.ps1` and
this document.

## Install

1. **Extract** to a permanent location — for example `C:\Tools\GCSViewer\`. The
   viewer runs from wherever you put it, so don't delete the folder.
2. Open **PowerShell** in the folder containing `GCSViewer.exe` and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-GcsViewer.ps1
   ```

   This registers the app for `.gcs` and `.gem` and gives those files a gem
   icon instead of a blank page. It copies nothing and needs no admin rights.

3. **Make it the default.** Windows lets only you do this, not the program —
   the setting is hash-protected so applications cannot claim file types behind
   your back.

   Right-click a `.gcs` file → **Open with** → **Choose another app** →
   **GCS Viewer** → **Always**, then repeat once on a `.gem` file. If
   **Always** is greyed out, select the app first; if GCS Viewer is not listed,
   scroll to the bottom for **Choose an app on your PC** and browse to
   `GCSViewer.exe`.

Gem Cut Studio, or whatever else you have, stays available on both file types
through **Open with**.

On first launch SmartScreen may ask about running an unsigned program — click
**More info → Run anyway**. That happens once.

## Using it

| Key | Does |
|---|---|
| **← →** | previous / next design in the folder, wrapping |
| **drag** | turn the 3/4 view left and right |
| **↑ ↓** | tip it up and down |
| **I** | show / hide the instructions table |
| **G** | grayscale |
| **L** | tier labels (T, C1, P1, …) |
| **S** | save the sheet as a PNG next to the design |
| **R** | reset the 3/4 angle |
| **Esc** / **Q** | close |

Files it cannot read are skipped while arrowing. Nothing is ever written to the
design file itself. Launching GCS Viewer from the Start Menu without a design
asks which one to open.

A panel reading **"no facets face this view"** is not a fault — a preform has
no crown yet, so there is nothing to draw from above.

### Command line

```powershell
.\GCSViewer.exe "C:\path\to\stone.gcs"                    # open the window
.\GCSViewer.exe "C:\path\to\stone.gcs" --save             # write a PNG, no window
.\GCSViewer.exe "C:\path\to\stone.gcs" --save --gray --no-labels
.\GCSViewer.exe --version                                 # which build is this
.\GCSViewer.exe --selftest report.txt                     # check the program is intact
```

Set `GCS_VIEWER_NO_GUI=1` when calling from a script: errors then print to the
console instead of opening a message box.

## Updating

Replace `GCSViewer.exe` — or the whole folder, for the folder build. The
association points at that path, so keep the name and location the same. If you
move it, re-run `Install-GcsViewer.ps1` from the new location and set the
default again, because Windows ties a saved choice to the app as it was
registered when you chose it.

To check what you are running: `.\GCSViewer.exe --version`, or look at the
window title.

## Uninstalling

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-GcsViewer.ps1
```

Then delete the folder. If you had set the viewer as the default, Windows keeps
that choice in a protected setting the script cannot remove — clear it in
**Settings → Apps → Default apps**, or pick another program with **Open with**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Double-click shows **"Select an app"** and choosing the viewer does nothing | Re-run `Install-GcsViewer.ps1`. Versions 1.0.19–1.0.25 registered the file type without a default action; re-running repairs it. |
| **GCSViewer.exe** appears twice in the list | Older versions left a duplicate registration. Re-running the installer removes it. |
| A default stops working after you move the program | Re-run the installer from the new location, then set the default once more. |
| SmartScreen: "Windows protected your PC" | **More info → Run anyway**, first launch only. |
| Every launch takes a second or so | Expected of the single-file build. Use the folder download. |
| "No facets found in file" | The file isn't a valid design, or is empty. |
| Nothing happens on double-click | Run `.\GCSViewer.exe "yourfile.gcs" --save` in PowerShell and read the error. |

*GCS Viewer is an independent viewer, not affiliated with Gemcut Studio,
GemCad, or their authors.*
