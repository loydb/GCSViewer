# GCS Viewer — Installation Guide

A small Windows app that shows a faceted gem from a **Gemcut Studio `.gcs`**
or **GemCad `.gem`** file as three shaded views — **table (top)**, **side**,
and a **3/4 view you can turn** — plus a **cutting-instructions table**
(tier, angle, indices, comments) like Gem Cut Studio's sequence panel.
`.gcs` files are tinted with the stone's own material colour; `.gem` files
(which don't store a colour) render as a neutral pale stone.
**Left/Right arrows step through the other designs in the folder.**
After installing, **double-clicking a `.gcs` or `.gem` file opens the viewer.**

There is nothing else to install. No Python, no libraries, no admin rights —
the interpreter and every library the viewer needs are inside it.

---

## Which download to take

Both are the same program, packaged two ways.

| | Starts in | Size on disk | Best for |
|---|---|---|---|
| **`GCSViewer.exe`** on its own | ~1.5 s | one 30 MB file | keeping on a USB stick, emailing to somebody, trying it out |
| **`GCSViewer-<version>-windows-folder.zip`** | ~0.4 s | ~70 MB in a folder | actually using it day to day |

The single file has to unpack its whole contents into `%TEMP%` **every time it
runs** — that is where the extra second goes, and it happens on every launch,
not just the first. The folder version is already unpacked. It is also the one
to use on a locked-down machine where policy stops programs running from
`%TEMP%`.

If you took the single `.exe` on its own, you can still register it — see
below — but you will want `Install-GcsViewer.ps1` from either zip.

---

## What's in this package

| File | Purpose |
|------|---------|
| `GCSViewer.exe` | The viewer. |
| `Install-GcsViewer.ps1` | Registers the "GCS Viewer" app for `.gcs` and `.gem` files. |
| `Uninstall-GcsViewer.ps1` | Removes the app registration. |
| `INSTALL.md` | This document. |

The folder download also contains an `_internal` folder full of libraries.
Leave it alone — the viewer will not start without it.

Nothing here needs administrator rights — everything installs for the
current user only.

---

## Install the viewer

1. **Extract** this zip to a permanent location — for example
   `C:\Tools\GCSViewer\`. The viewer runs from wherever you put it, so don't
   delete the folder afterward.
2. Open **PowerShell** and change into the folder that contains
   `GCSViewer.exe`, e.g.:

   ```powershell
   cd C:\Tools\GCSViewer
   ```

3. Run the installer:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Install-GcsViewer.ps1
   ```

   This registers a **"GCS Viewer"** application for `.gcs` **and** `.gem`
   files, and gives those files a gem icon in Explorer instead of a blank
   page. (It does not copy any files or change anything else.)

   > **Tip:** if PowerShell blocks the script, the `-ExecutionPolicy Bypass`
   > above already handles it. You do **not** need to run as Administrator.

4. **Set GCS Viewer as the default (one time, per file type).** Windows does
   not let a program make itself the default for a file type — *you* have to
   pick it once:

   - In File Explorer, **right-click any `.gcs` file** →
     **Open with** → **Choose another app**.
   - Click **GCS Viewer** to select it.
   - Click **Always**. (Windows 11 shows **Always** and **Just once** buttons
     at the foot of the dialog. Older versions instead show a checkbox reading
     *"Always use this app to open .gcs files"* — tick it, then **OK**.)
   - **Repeat once for a `.gem` file.** Windows tracks the default separately
     per file type, so setting `.gcs` does nothing for `.gem`.

   **If "GCS Viewer" isn't in the list** (common on Windows 11): scroll to the
   bottom of the dialog and click **Choose an app on your PC** (older Windows:
   **More apps** → **Look for another app on this PC**), browse to
   **`GCSViewer.exe`** where you extracted this package, then **Always**.

   **If a design program is already installed,** it very likely claims `.gcs`
   and `.gem` too, and the dialog may pre-select it. Check that the **GCS
   Viewer** entry is the highlighted one before you commit. Setting the viewer
   as the default does not remove the other program — it stays available on
   both file types through **Open with**, it just stops being what a
   double-click reaches.

   From now on, **double-clicking a `.gcs` or `.gem` file opens the viewer.**

   > Windows blocks programs from setting themselves as the default for a file
   > type. The setting lives in a registry value carrying a hash and a deny
   > ACE, so that only the shell can write it — which is why this step is
   > manual, and why anything claiming to automate it is either forging that
   > hash or not working.

> **First launch note:** Windows SmartScreen may ask whether you want to run
> an unsigned program downloaded from the internet — click
> **More info → Run anyway**. That happens once.

---

## Using the viewer

- **Left / Right arrows** — step to the previous / next `.gcs` or `.gem` file
  in the same folder (wraps around), just like the Windows photo viewer.
  Files it cannot read are skipped rather than stopping the walk.
- **Drag** the 3/4 view with the mouse to turn the stone left and right.
- **Up / Down arrows** — tip it up and down.
- **I** — toggle the **Instructions** table below the renders (tier name,
  cutting angle, index list, and the cutting instruction / comment, grouped
  into Pavilion and Crown — like the Gem Cut Studio sequence panel).
- **G** — toggle grayscale / colour.
- **L** — toggle the tier labels (T, C1, P1, …).
- **S** — save the current views (with the instructions table) as a PNG next
  to the design. Nothing is ever written to the design file itself.
- **R** — reset the 3/4 angle.
- **Esc** or **Q** — close.

Launching **GCS Viewer** from the Start Menu without a design asks which one
to open.

A panel that reads **"no facets face this view"** is not a fault. A preform —
a stone with the girdle and pavilion cut but no crown yet — has nothing at all
facing the table view, so there is genuinely nothing to draw.

### Command line (optional)

```powershell
# open the interactive window
.\GCSViewer.exe "C:\path\to\stone.gcs"

# just write a PNG (no window) next to the file
.\GCSViewer.exe "C:\path\to\stone.gcs" --save

# grayscale, or hide tier labels
.\GCSViewer.exe "C:\path\to\stone.gcs" --save --gray --no-labels

# which build is this?  (also shown in the window's title bar)
.\GCSViewer.exe --version

# check the program itself is intact - renders a stone it builds in memory
.\GCSViewer.exe --selftest report.txt
```

Set the environment variable `GCS_VIEWER_NO_GUI=1` if you are calling the
viewer from a script: errors then print to the console instead of opening a
message box that nobody is there to dismiss.

---

## Updating

Replace `GCSViewer.exe` in the install folder with the new version — for the
folder build, replace the whole folder. The file association points at that
path, so no re-install is needed as long as the name and location stay the
same.

**If you move it**, re-run `Install-GcsViewer.ps1` from the new location — and
expect Windows to ask which program to use the next time you double-click a
design. Changing the path invalidates the default you picked, so you set it
once more, exactly as in step 4. Moving between the single-file and folder
downloads counts as moving it.

To check what you are running, look at the window's title bar, or run
`.\GCSViewer.exe --version`.

---

## Uninstalling

From the install folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-GcsViewer.ps1
```

This removes the `.gcs` and `.gem` associations. Then simply delete the
folder — the viewer doesn't install anything anywhere else.

If you had set it as the *default* with "Always use this app", Windows keeps
that choice in a protected setting the script cannot remove; clear it in
**Settings → Apps → Default apps**, or just pick a different program with
**Open with → Choose another app**.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Windows SmartScreen: "Windows protected your PC" | Click **More info → Run anyway** (first launch only). |
| Every launch takes a second or so | Expected of the single-file build — it unpacks itself each time. Use the folder download instead. |
| Double-click opens a different program | Re-set the default with **Open with → Choose another app** (see above). |
| Not sure which version you have | Look at the title bar, or run `.\GCSViewer.exe --version`. |
| "The file is empty (0 bytes)" | The file really is empty — nothing to show. Restore it from a backup. |
| "No facets found in file" | The file isn't a valid design, or is corrupt. |
| A panel says "no facets face this view" | Not a fault — see above. |
| Nothing happens on double-click | Run `.\GCSViewer.exe "yourfile.gcs" --save` in PowerShell and check for an error window. |

---

*GCS Viewer is an independent viewer and is not affiliated with Gemcut Studio,
Gem Cut Studio, GemCad or their authors.*
