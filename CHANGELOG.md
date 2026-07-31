# Changelog

Every release is built, self-tested and published by
[the release workflow](.github/workflows/release.yml), which also refuses to
publish a tag that disagrees with `__version__` and refuses to ship an
executable whose frozen code does not match the committed source.

## 1.0.32

- Documented the save behaviour introduced by the security pass: a defaulted
  output name is never overwritten, so a second save lands beside the first as
  `stone_views (1).png`. An explicitly given name is used as given.
- Corpus verification of that security pass, since it changed the parsing API
  the solver imports. Old parser against new across **9,146 `.gcs` files**: no
  file newly rejected by the resource caps, no facet-count difference. Across
  **245 `.gem` files**: no failures, no facet-count changes, and **12 titles
  improved** — bounding the trailing-string sweep stopped it latching onto a
  mid-note offset and returning note fragments as the title, so *soda_bar_19*
  now reads "Soda Bar 19" instead of "Are Given for Ordinary Soda-li…".
  One file, `kansas__kansas.gem`, lost its note block in that change.

## 1.0.31

- Building the executable moves to DEVELOPING.md. **Run from source** stays in
  the README, now saying what it is for: it is how to use the viewer on Mac or
  Linux, where the download is no use. Corrected the invocation there —
  `pythonw` is Windows-only.

## 1.0.30

- Documentation only. The test suites, the verification tooling and the
  constraints on the shared parsing API move out of the README into
  DEVELOPING.md; the README is now about using the program.

## 1.0.29

- Documentation only. README and INSTALL.md cut roughly in half; the reference
  material is unchanged. Entries in this file rewritten as release notes, and a
  duplicated 1.0.26 heading merged.

## 1.0.28

- `scripts/Show-OpenWithList.ps1` now checks whether a double-click resolves to
  a program that exists, not only whether the viewer appears in the open-with
  list. It walks the chain the shell walks — effective ProgId, its default verb,
  that verb's command, the program itself — and names the missing link. A file
  type with no default verb is reported as such, with the instruction to re-run
  the installer.
- It also reports stale shell display names, which a moved or uninstalled
  program leaves behind and which surface as a dead row in the picker. Scoped to
  this program's executables: unscoped it matched 475 entries from unrelated
  applications.

## 1.0.27

- `scripts/test_installer.ps1` runs the installer against a throwaway ProgId,
  extension and app name, reads all 22 registrations back out of the registry,
  then runs the uninstaller and checks every one is gone. No real association is
  touched, and it cleans up even if a check throws. CI runs it on the Windows
  jobs.
- The textual installer checks stay, since they catch a deleted line on Linux
  too, but only a registry read proves the file type actually works.

## 1.0.26

- **Fixed: double-clicking a design opened the "Select an app" dialog, and
  choosing the viewer did nothing.** The ProgId's `shell` key had no default
  value, so nothing declared which verb a double-click invokes: the file type
  resolved, the icon appeared, the command was correct, Settings showed the
  right default, and Explorer had no action to run. Affects 1.0.19–1.0.25.
  **Re-run `Install-GcsViewer.ps1` to repair it.**
- **The installer removes the ProgId `Application` subkey that 1.0.19–1.0.25
  wrote**, so re-running repairs a machine that ran one of those versions. It
  was added on the theory that Settings → Default apps needed it; it did not
  help there, and because it declares the document type to be an application it
  listed the program twice in the open-with dialog and stopped Explorer
  honouring the class association.
- The installer clears shell display-name entries for executable paths that no
  longer exist, which showed as a second, dead row in that dialog.
- The installer has tests — 17, reading the script — where it previously had
  none. That is how a missing default verb reached five releases.
- Corrected two documentation claims: the `Capabilities` registration is not
  what puts the program in the picker (the `Applications` entry is), and the
  1.0.25 note below blamed the wrong cause.

## 1.0.25

- Documented a diagnosis that was **wrong** — see 1.0.26 for the actual cause.
  Left in place rather than deleted: every registry key was correct, which is
  what made a cache look like the explanation, and a reboot disproved it.
- Documented why the program can appear twice in the open-with list, and that a
  saved default does not survive the program being moved.

## 1.0.24

- **The moved-install warning now gives advice that actually works.** It said
  "set it again", which is precisely what Windows refuses: the stale entry
  already names this app, so re-picking it is not a change and the **Always**
  button is greyed out. Set-but-invalid, and unfixable by picking the same
  app. The warning now spells out the two-step escape — pick another program
  and confirm, then pick GCS Viewer — which makes the second pick a real
  change Windows will accept.

## 1.0.23

- **The install guide told you to extract both downloads the same way, and
  they unpack differently.** The single-file zip puts its files at the root;
  the folder zip contains a `GCSViewer` folder. Following the old
  instruction with the folder download gave `GCSViewer\GCSViewer\`. Now
  documented per download, with a note that the installer registers whichever
  `GCSViewer.exe` sits beside it — so step 2 must be the folder holding the
  `.exe`, not its parent.

## 1.0.22

- **The installer now notices when the program has moved** and says which file
  types it broke. Windows ties a default you explicitly picked to the app
  registration as it stood at the time, so moving the install silently kills
  it — a double-click then does nothing at all, with no fallback and no
  prompt. A type you never explicitly set is unaffected: it resolves through
  the registration the installer rewrites, and follows the move by itself.
  The installer records where it registered, so the next run can tell the two
  apart instead of leaving you to find out by double-clicking.

## 1.0.21

- **The executable now describes itself.** It carried no Windows version
  resource, so everywhere the shell asks a program what it is called — the
  Properties tab, Task Manager, the name cache the Open-with lists draw on —
  Windows fell back to the filename and showed `GCSViewer.exe`. It now
  reports **GCS Viewer** with its version, generated from `__version__` at
  build time so it cannot drift from the tag.
- Easy to miss, because the Open-with entry reads its name from the registry
  and looked correct while every other surface in Windows showed the filename.

## 1.0.20

- **The app now appears in Settings → Apps → Default apps.** The ProgId had
  no `Application` subkey, which is how a ProgId declares itself an
  application rather than a file type with a handler — and that Settings page
  builds its per-extension list from ProgIds, naming each from that subkey.
  With 1.0.19's Default Programs registration this makes three separate
  registrations, one per place Windows might offer the app; the README has
  the table.

## 1.0.19

- **The installer now registers the app with Default Programs**
  (`RegisteredApplications` plus a `Capabilities` key). Without it Windows 11
  builds its "Select an app to open this file" list without GCS Viewer in it,
  even though the handler was correctly registered — the app was reachable
  only by browsing to the .exe by hand, and did not appear in Settings →
  Default apps at all. Found by watching the dialog rather than the registry.
- Setting the default is now documented as its own section, with the Settings
  route (which works when another program already owns the file type), the
  Open-with route, and the two things that trip both up: **Always** only
  appears once an app is selected, and a missing app means the installer was
  not run from the folder holding that `GCSViewer.exe`.

## 1.0.18

- The installation guide, rewritten around the step people actually get stuck
  on. It now describes the dialog Windows 11 really shows (**Always** /
  **Just once** buttons, not the old checkbox), says that a design program
  already on the machine claims these extensions too and may be pre-selected,
  and makes clear that choosing the viewer does not remove it — it stays on
  **Open with**. Moving an install invalidates the default and brings that
  dialog back, which is now said out loud under Updating.
- `build_exe.py` installs over the copy Windows actually launches, read from
  the registry rather than assumed, and refuses to write a single-file build
  over a folder install or the reverse.
- No change to the program itself.

## 1.0.17

- **What `write_gcs` writes no longer depends on the machine writing it.**
  Handing ElementTree a path makes it open the file itself, in text mode with
  the local code page — CRLF on Windows, LF elsewhere, and a title outside
  that code page raises instead of being written. Output is now UTF-8 with LF
  everywhere. Found by CI: a demo stone generated on Windows and regenerated
  on Linux did not match.

## 1.0.16

- The windowed suite now presses the keys rather than calling the methods
  behind them, through Tk's own event dispatch. Everything it checked before
  would have passed with a binding removed or bound to the wrong key; two
  mutations now prove otherwise.

## 1.0.15

- Browsing checks: the caches that make arrowing quick must not grow with the
  walk. Measured alongside them — 200 steps through a 996-design folder ends
  0.3 MB below where it started, with all three caches pinned at their bounds.

## 1.0.14

- **The Start Menu shortcut did nothing.** The installer creates one —
  Windows 11 builds its Open-With list from registered applications, so it
  has to — and clicking it launched the viewer with no file named, which
  printed usage to a console a windowed build does not have and exited 2.
  Launching without a file now asks which design to open. Scripted callers
  keep the old contract: with `GCS_VIEWER_NO_GUI` set it still prints usage
  and exits 2.

## 1.0.13

- `test_gui.py`: 26 checks on the part of the program a user actually
  operates — stepping through a folder with the arrow keys, wrapping past the
  ends, skipping designs it cannot read, the tilt limits, the toggles, and
  saving. It drives the real widgets and pumps Tk's event loop by hand, and
  skips itself where there is no display.
- The mutation harness runs both suites and judges three window-only defects,
  reporting them as *unjudged* rather than passed where Tk cannot open. 22 of
  22 caught.

## 1.0.12

- **Converting a `.gem` no longer drops cutting steps.** `write_gcs` wrote the
  instruction the tier opens with and discarded the rest; 332 of the `.gem`
  files in the reference collection lost at least one. It now joins the
  distinct steps into the single string the format allows, the same way the
  table displays them.

  This had been left as the owner's call, on the grounds that ~29 solver
  scripts import `write_gcs` and a longer instruction string might break
  something that matches on the text. Measuring it settled it: of 92 scripts
  that touch that tree, exactly one reads the converted `.gcs` output — the
  converter itself — and none reads instructions from it. Every other script
  reads the `.gem` originals directly, as a geometry oracle.

## 1.0.11

- The designer's notes carried in a `.gem` are printed along the foot of the
  sheet. The reader had been extracting them since 2026-07-13 and nothing
  displayed them, while the footer sat empty on exactly those files.

## 1.0.10

- The setup guide that ships inside both release zips brought back in line
  with the program. It had said the single-file build is only slow on its
  first launch; it unpacks itself on **every** launch, which is why the
  folder build exists.

## 1.0.9

- Releases now carry a **folder build** as well as the single file. The
  single file unpacks its whole contents into `%TEMP%` every time it runs —
  1,534 ms to start, against 427 ms unpacked.
- `--version` reaches a terminal. A `--windowed` build has no console of its
  own, and CPython's `print()` returns silently when `sys.stdout` is `None`,
  so it attaches to the parent process's console when there is one.

## 1.0.8

- The viewer reports its version — in the title bar and via `--version`,
  along with whether it is the frozen executable or the source. Handed out as
  a bare `.exe` there was no way to tell one build from another, which is how
  a stale one goes unnoticed.

## 1.0.7

- Stepping between designs no longer re-lists the folder twice per keypress.
  On a 996-design folder that was 52 ms per press, more than the parse and
  render it wrapped; now 0.03 ms, and 2.4 ms cold.

## 1.0.6

- The cutting table is no longer redrawn on every frame of a drag. It was 40%
  of a frame on an ordinary design and two thirds of one at 4,200 facets.
  Drags are 1.5× faster typically, 3.2× on the heavy case.

## 1.0.5

- A panel with nothing facing it says so instead of showing black. A preform
  has no crown, so its table view is legitimately empty — truthful, but
  indistinguishable from a viewer that broke.
- `scripts/render_audit.py`: measures how much of each panel is actually
  drawn, because a crash-free render sweep will happily pass a stone drawn
  inside out. Over 8,984 designs it found no inverted normals.

## 1.0.4

- **The copyright line is gone from rendered sheets.** Every sheet carried a
  notice for the author of the viewer, including sheets of designs cut or
  drawn by somebody else. The footer now shows only what the design file
  itself states.

## 1.0.3

Three defects found by sweeping 10,249 real designs:

- **A design whose title is not ASCII would not open at all.** Gem Cut Studio
  writes the file in the machine's code page and declares no encoding, so
  *Viet Gems 216 — Fleur en rêve* was rejected as malformed XML over one byte
  in its title.
- **`write_gcs` merged tiers that share a name.** Two `<tier>` elements may
  carry the same name; one design was rewritten from nine tiers to one.
  Boundaries now follow the element, and only where that splits a tier.
- Zero-byte files said "no element found: line 1, column 0". They now say the
  file is empty.

## 1.0.2

- **Cutting steps were being dropped.** In a `.gem` the instruction belongs to
  the facet that *begins* a step and a tier can hold several — 144 lines lost
  across 56 of the 245 `.gem` files in the reference collection.
- `scripts/corpus_scan.py`: parses every design under a folder, optionally
  rendering a sample and round-tripping each file through `write_gcs`.

## 1.0.1

- An icon, drawn by the renderer itself, compiled into the executable and
  registered for `.gcs` and `.gem` documents — a file-type handler with no
  icon leaves Explorer showing a blank page for every design in the folder,
  which is most of what this tool exists to fix.

## 1.0.0

First public release. Three shaded views and the cutting sequence from a
`.gcs` or `.gem` file, on a double-click.

Published with the apparatus the project had never had: a 100-plus check
suite that synthesises its own `.gem` binaries from an independent encoder, a
mutation harness that proves those checks can fail, and a tool that diffs the
code frozen inside a PyInstaller executable against the current source —
written because the executable in this project's history was four weeks
behind the `.py` it was supposedly built from.
