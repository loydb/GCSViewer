# GCS Viewer — Installation Guide

A small Windows app that shows a faceted gem from a **Gemcut Studio `.gcs`**
or **GemCad `.gem`** file as three shaded views — **table (top)**, **side**,
and a **3/4 view you can spin** — plus a **cutting-instructions table**
(tier, angle, indices, comments) like Gem Cut Studio's sequence panel.
`.gcs` files are tinted with the stone's own material colour; `.gem` files
(which don't store a colour) render as a neutral pale stone.
**Left/Right arrows step through the other designs in the folder.**
After installing, **double-clicking a `.gcs` or `.gem` file opens the viewer.**

The viewer is a **single standalone program** — there is nothing else to
install. No Python, no libraries, no admin rights.

---

## What's in this package

| File | Purpose |
|------|---------|
| `GCSViewer.exe` | The viewer — a complete, self-contained program. |
| `Install-GcsViewer.ps1` | Registers the "GCS Viewer" app for `.gcs` and `.gem` files. |
| `Uninstall-GcsViewer.ps1` | Removes the app registration. |
| `INSTALL.md` | This document. |

Nothing here needs administrator rights — everything installs for the
current user only.

---

## Install the viewer

1. **Extract** this zip to a permanent location — for example
   `C:\Tools\gcs-viewer\`. The viewer runs from wherever you put it, so don't
   delete the folder afterward.
2. Open **PowerShell** and change into that folder, e.g.:

   ```powershell
   cd C:\Tools\gcs-viewer
   ```

3. Run the installer:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-GcsViewer.ps1
   ```

   This registers a **"GCS Viewer"** application for `.gcs` **and** `.gem`
   files. (It does not copy any files or change anything else.)

   > **Tip:** if PowerShell blocks the script, the `-ExecutionPolicy Bypass`
   > above already handles it. You do **not** need to run as Administrator.

4. **Set GCS Viewer as the default (one time).** For security, Windows does
   not let a program silently make itself the default for a file type — *you*
   have to pick it once:

   - In File Explorer, **right-click any `.gcs` file** →
     **Open with** → **Choose another app**.
   - Pick **GCS Viewer** from the list.
   - **If "GCS Viewer" isn't in the list** (common on Windows 11): scroll to
     the bottom of the dialog and click **Choose an app on your PC** (on older
     Windows: **More apps** → **Look for another app on this PC**). Then browse
     to **`GCSViewer.exe`** in the folder where you extracted this package and
     select it.
   - Tick **Always use this app to open .gcs files** → **OK**.
   - **If you also have `.gem` files,** repeat this once for a `.gem` file —
     Windows tracks the default separately per file type.

   From now on, **double-clicking a `.gcs` or `.gem` file opens the viewer.**

   > Windows blocks programs from setting themselves as the default for a file
   > type — only you can, through this dialog. That's why this step is manual.

> **First launch note:** the very first time the viewer opens it may take a
> few extra seconds (it unpacks itself), and Windows SmartScreen may ask if
> you want to run it — click **More info → Run anyway**. Both happen only
> once.

---

## Using the viewer

- **Left / Right arrows** — step to the previous / next `.gcs` or `.gem` file
  in the same folder (wraps around), just like the Windows photo viewer.
- **Drag** the 3/4 view with the mouse to spin the stone.
- **Up / Down arrows** — tilt the 3/4 view.
- **I** — toggle the **Instructions** table below the renders (tier name,
  cutting angle, index list, and the cutting instruction / comment, grouped
  into Pavilion and Crown — like the Gem Cut Studio sequence panel).
- **G** — toggle grayscale / colour.
- **L** — toggle the tier labels (T, C1, P1, …).
- **S** — save the current views (with the instructions table) as a PNG.
- **R** — reset the 3/4 angle.
- **Esc** or **Q** — close.

### Command line (optional)

```powershell
# open the interactive window
.\GCSViewer.exe "C:\path\to\stone.gcs"

# just write a PNG (no window) next to the file
.\GCSViewer.exe "C:\path\to\stone.gcs" --save

# grayscale, or hide tier labels
.\GCSViewer.exe "C:\path\to\stone.gcs" --save --gray --no-labels

# check the program itself is intact - renders a stone it builds in memory
.\GCSViewer.exe --selftest report.txt
```

Set the environment variable `GCS_VIEWER_NO_GUI=1` if you are calling the
viewer from a script: errors then print to the console instead of opening a
message box that nobody is there to dismiss.

---

## Updating

Replace `GCSViewer.exe` in the install folder with the new version. The file
association points at that path, so no re-install is needed. (If you move the
folder, re-run `Install-GcsViewer.ps1` from the new location.)

---

## Uninstalling

From the install folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-GcsViewer.ps1
```

This removes the `.gcs` and `.gem` associations. Then simply delete the
folder — the viewer doesn't install anything anywhere else.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Windows SmartScreen: "Windows protected your PC" | Click **More info → Run anyway** (first launch only). |
| First launch is slow | Normal — the program unpacks itself the first time. Later launches are faster. |
| Double-click opens a different program | Re-set the default with **Open with → Choose another app** (see above). |
| "No facets found in file" | The file isn't a valid Gemcut Studio `.gcs`, or is empty/corrupt. |
| Nothing happens on double-click | Run `.\GCSViewer.exe "yourfile.gcs" --save` in PowerShell and check for an error window. |

---

*GCS Viewer is an independent viewer and is not affiliated with Gemcut Studio
or SingleCellSoftware.*
