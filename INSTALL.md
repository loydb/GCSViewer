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

1. **Extract** this zip to a permanent location. The viewer runs from
   wherever you put it, so don't delete the folder afterward.

   The two downloads unpack differently, so extract them to different places:

   | Download | Extract to | You end up with |
   |---|---|---|
   | `GCSViewer-<version>-windows.zip` | the folder you want it in, e.g. `C:\Tools\GCSViewer` | files directly in that folder |
   | `GCSViewer-<version>-windows-folder.zip` | the **parent**, e.g. `C:\Tools` | `C:\Tools\GCSViewer\` |

   The folder download already contains a `GCSViewer` folder. Extracting it
   *into* one called `GCSViewer` gives you `GCSViewer\GCSViewer\`, which works
   but reads badly and makes the path you have to type twice as long.

2. Open **PowerShell** and change into the folder that contains
   `GCSViewer.exe` — the installer registers whichever copy sits beside it,
   so this must be the folder holding the `.exe`, not its parent:

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

4. **Make it the default.** Windows does not allow a program to make itself
   the default for a file type, so this last step is yours — **once for
   `.gcs` and once for `.gem`**, which Windows tracks separately.

   **The reliable way — Settings.** Use this if another program is already
   opening these files.

   1. Open **Settings** → **Apps** → **Default apps**.
   2. In the box labelled **Set a default for a file type or link type**,
      type `.gcs`.
   3. Click the **.gcs** row that appears — it shows the current default, or
      **Choose a default**.
   4. Pick **GCS Viewer**, then click **Set default**.
   5. Repeat from step 2 for `.gem`.

   **The quicker way — from a file.** Right-click any `.gcs` file →
   **Open with** → **Choose another app**, click **GCS Viewer**, then click
   **Always**. Repeat on a `.gem` file.

   Two things that trip this up:

   - The dialog offers only **Just once** until you actually select an app.
     Click the app first and **Always** appears.
   - If **GCS Viewer** is not in the list at all, scroll to the very bottom
     and click **Choose an app on your PC** (older Windows: **More apps** →
     **Look for another app on this PC**), then browse to `GCSViewer.exe` in
     the folder you extracted. If that happens, `Install-GcsViewer.ps1` was
     probably not run from the folder holding that same `GCSViewer.exe`.

   Setting the viewer as the default removes nothing. Gem Cut Studio, or
   whatever else you have, stays available on both file types through
   **Open with** — it just stops being what a double-click reaches.

   From now on, **double-clicking a `.gcs` or `.gem` file opens the viewer.**

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

**If you move it**, re-run `Install-GcsViewer.ps1` from the new location. The
installer remembers where it last registered, so it will tell you if the copy
moved and which file types are affected.

If a default you set has gone stale, **re-picking the viewer will not fix it
on its own.** The stale entry already names this app, so Windows sees no
change and greys out **Always**. Pick a different program (Notepad will do)
and confirm with **Always**, then pick GCS Viewer the same way — the first
step replaces the stale entry, which makes the second a real change.

Moving breaks a default you **explicitly set**, and only that. Windows ties a
saved choice to the app registration as it stood when you picked it, so after
a move a double-click on that type does nothing at all — it does not fall back
and it does not prompt. Set it once more, exactly as in step 4. A file type
you never explicitly set follows the move on its own, because it resolves
through the registration the installer rewrites. Moving between the
single-file and folder downloads counts as moving it.

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
| Double-click shows **"Select an app to open this file"** even though the default is already set | Explorer caches file associations for the life of its session, and a cached entry outlives the registry. **Sign out and back in, or reboot.** To confirm that is what it is: open PowerShell and run `Start-Process "C:\path	o\stone.gcs"` — if it opens the viewer from there but Explorer still prompts, the registration is correct and only the cache is stale. |
| **GCSViewer.exe** appears twice in the list | Two registrations legitimately resolve to the same program: the document type (`GcsViewer.Stone`) and the application entry (`Applications\GCSViewer.exe`). Either works. Both exist because the second is what "Choose an app on your PC" attaches to. |
| A default you set stops working after the program is moved | Windows binds a saved default to the app as it was registered when you picked it. Re-run `Install-GcsViewer.ps1` from the new location and set the default once more — the installer warns you when it detects this. |
| Double-click opens a different program | Re-set the default with **Open with → Choose another app** (see above). |
| Not sure which version you have | Look at the title bar, or run `.\GCSViewer.exe --version`. |
| "The file is empty (0 bytes)" | The file really is empty — nothing to show. Restore it from a backup. |
| "No facets found in file" | The file isn't a valid design, or is corrupt. |
| A panel says "no facets face this view" | Not a fault — see above. |
| Nothing happens on double-click | Run `.\GCSViewer.exe "yourfile.gcs" --save` in PowerShell and check for an error window. |

---

*GCS Viewer is an independent viewer and is not affiliated with Gemcut Studio,
Gem Cut Studio, GemCad or their authors.*
