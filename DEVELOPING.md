# Developing

Notes for changing this code. Everything a user needs is in
[README.md](README.md) and [INSTALL.md](INSTALL.md).

## The shared parsing API

`parse_gcs`, `parse_gem`, `write_gcs` and `load_design` are imported by a
separate, unpublished pipeline that reconstructs faceting designs from scanned
diagrams. They are a shared surface with a real dependent, so changes are
additive: new optional parameters, never a changed signature or a changed
meaning. The parser checks in `test_gcs_viewer.py` are the contract.

## Build the exe

```bash
python scripts/build_exe.py --clean       # single file
python scripts/build_exe.py --onedir      # folder build
```

Both shapes are attached to every release. The build then updates the copy
Windows actually launches, reading that path out of the `.gcs` association
rather than assuming it; `--no-install` skips that. It refuses to write a
single-file exe over a folder install, or the reverse.

An unsigned executable downloaded from the internet trips SmartScreen until it
earns reputation: expect **More info → Run anyway** once.

```bash
python scripts/compare_exe_source.py GCSViewer.exe gcs_viewer.py
```

An exe carries its entry script as a marshalled code object, so there is no
source inside to diff — but every function's signature, docstring, constants
and bytecode can be compared exactly. It answers the question that matters
after an edit: is the shipped exe still this source? The release workflow runs
it and refuses to publish a mismatch.

```bash
python scripts/make_demo.py         # docs/demo.gcs and docs/demo.png
python scripts/make_demo_anim.py    # the animation at the top of this page
python scripts/gen_icon.py          # docs/gcsviewer.ico
python scripts/check_demo.py        # the committed stone matches its generator
```

![the icon at 16, 24, 32, 48, 64, 128 and 256 pixels](docs/icon-preview.png)

The icon is the demo stone drawn by the viewer's own renderer, so it cannot
drift from what the program produces.

## Tests

```bash
python test_gcs_viewer.py     # 197 checks
python test_gui.py            # 37 checks, the window itself
```

No fixtures on disk and no third-party design files: every stone is
synthesised by the suite, **including the `.gem` binaries**, which are written
by a miniature encoder built from the format notes. A parser tested only
against files it already parses proves nothing about the format.

`test_gui.py` drives the real widgets and pumps Tk's event loop by hand rather
than calling `mainloop()`, and presses the actual keys through Tk's event
dispatch. It skips where Tk has no display, so headless runners stay green.

```bash
python scripts/mutation_check.py
```

Reintroduces twenty-six deliberate defects one at a time — dropping the `.gem`
Y mirror, painting nearest-first, ignoring the gear — and reports which checks
catch each. Currently **26 of 26**. Its first run found three that survived,
which is why the suite now builds deliberately non-convex scenes: a convex
stone hides its own back faces *and* tiles its silhouette, so the cull and the
depth sort can both break without changing a pixel.

```bash
powershell -ExecutionPolicy Bypass -File scripts/test_installer.ps1
```

Installs against a throwaway ProgId, extension and app name, reads all 22
registrations back out of the registry, then runs the uninstaller and checks
every one is gone. No real association is touched.

### Against real files

```bash
python scripts/corpus_scan.py "D:\designs" --render 150 --roundtrip
```

Synthetic stones prove the format; they cannot prove twenty years of files
written by other people's programs. This parses every `.gcs` and `.gem` under a
folder and, with `--roundtrip`, writes each back out through `write_gcs` and
re-reads it.

Run over a collection of **10,249 designs** it found four defects the
synthetic suite could not, all fixed:

- **A design whose title is not ASCII would not open.** Gem Cut Studio writes
  the machine's code page and declares no encoding, so one byte in *Viet Gems
  216 — Fleur en rêve* made the whole file malformed XML. The reader now falls
  back through the Windows code pages.
- **Cutting steps were dropped.** In a `.gem` the instruction belongs to the
  facet that *begins* a step and a tier can hold several: 144 lines lost across
  56 of 245 files.
- **`write_gcs` merged tiers sharing a name** — one design went from seven
  tiers to one. Boundaries now follow the element, not the label.
- **Zero-byte files reported a parser error** rather than saying they were
  empty. Twelve sit in that collection.

Afterwards: no parse failures, no malformed geometry, every design
round-trips with vertices bit-exact and no tier lost.
