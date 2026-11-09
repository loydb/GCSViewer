#!/usr/bin/env python
r"""
gem_import_probe.py - what does Gem Cut Studio itself put in a .gcs when it
imports a .gem?

    python scripts\gem_import_probe.py            all staged .gem files
    python scripts\gem_import_probe.py --only "1210 Oval"

WHY
---
A .gem's second trailing string is a free-text SUBTITLE, not an author: of
447 corpus files only 58 start with "by", the rest hold dates ("April 2019"),
competition names ("2008 USFG Single Stone Competition") and attributions
("from Paul C. Smith Sirus").  write_gcs must put it, and the comment lines
below it, wherever Gem Cut Studio puts them - and no file can answer that.
So: import the .gem in GemCut, Save As .gcs, and read the fields back.

Gem Cut Studio's own files use <info title author date ri_min ri_max shape
header2 header3 footer1..footer4> and <render material refractive_index
dispersion clarity density lighting_model>, so the slots exist; which ones
the import fills is the question.

SAFETY
------
Reads the staged .gem files in IN_DIR and writes .gcs only into OUT_DIR.  It
never touches all-files-by-shape, the plugin build, or the server assets.
GemCut rewrites its config (RENDER_HIGH_RES among it) when it EXITS, so this
never closes the app - check and close by hand afterwards.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILT = r"D:\GCS Raytracer\tilt performance\Scripts"
PRINT = r"D:\GCS Raytracer\gcs print\Scripts"
for p in (TILT, PRINT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

IN_DIR = os.path.join(HERE, "local", "gem-import-test")
OUT_DIR = os.path.join(IN_DIR, "gemcut-saved")


def _norm(t: str) -> str:
    """OCR text with its trailing punctuation and spacing taken off."""
    return t.strip().strip(".:… 	").lower()


def _find_item_loose(hwnd, want: str, region):
    """(x, y) of the menu item whose OCR text matches `want` once both have
    had their trailing punctuation removed; None if no row matches."""
    import gemcut_ui
    from probe_print_click import reader
    img = gemcut_ui.capture_screen(hwnd)
    x0, y0, x1, y1 = region
    crop = img[y0:y1, x0:x1]
    for box, text, _conf in reader().readtext(crop):
        if _norm(text) == _norm(want):
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            return (x0 + int(sum(xs) / 4), y0 + int(sum(ys) / 4))
    return None


def save_as(sess, out_path: str):
    """File > Save As..., into out_path.

    The File menu's items are found by their text, the way the sheet printer
    finds "Print..." - there is no template for Save As and one more template
    to keep in step with the theme is not worth it for a one-off probe."""
    import gemcut_ui
    from gemcut_tilt import StepFailed
    from gemcut_drive import click, to_screen
    from probe_print_click import find_item

    sess.open_menu("menu_file", "item_file_open")
    g = gemcut_ui.geometry(sess.hwnd)
    hit = sess.see("menu_file", 0.85)
    if not hit:
        raise StepFailed("File menu label vanished")
    region = (max(0, hit[0] - 40), hit[1] + 10,
              min(g["size"][0], hit[0] + 900), min(g["size"][1], hit[1] + 900))
    # Matched leniently.  find_item() (the sheet printer's) compares the OCR
    # text for equality after stripping dots, and easyocr reads this entry as
    # "save as:" - a colon it did not have.  Normalising the trailing
    # punctuation off both sides is the difference between finding it and not.
    pt = _find_item_loose(sess.hwnd, "Save As", region)
    if pt is None:
        pt, hits = find_item(sess.hwnd, "Save As...", region, "gem_probe_menu")
    if pt is None:
        raise StepFailed('no menu item reading "Save As...": %s'
                         % ", ".join(h[0] for h in hits[:16]))
    click(*to_screen(sess.hwnd, *pt))
    dlg = sess._native(20.0)
    sess._fill_native(dlg, out_path, "&Save")
    t0 = time.time()
    while time.time() - t0 < 60:
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            time.sleep(0.6)
            return
        time.sleep(0.2)
    raise StepFailed("Save As wrote nothing in 60 s: %s" % out_path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring of the .gem filename")
    a = ap.parse_args(argv)

    import gemcut_ui
    from gemcut_tilt import TiltSession

    # start_app maximizes; a non-maximized window makes every settle check
    # time out (and GemCut reads its config, RENDER_HIGH_RES included, here)
    if not gemcut_ui.find_windows():
        print("Gem Cut Studio is not running; starting it maximized")
        gemcut_ui.start_app()
        time.sleep(1.5)

    gems = sorted(f for f in os.listdir(IN_DIR) if f.lower().endswith(".gem"))
    if a.only:
        gems = [g for g in gems if a.only.lower() in g.lower()]
    if not gems:
        sys.exit("no staged .gem files in %s" % IN_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    sess = TiltSession()
    sess.ensure_idle()
    done, failed = [], []
    for name in gems:
        src = os.path.join(IN_DIR, name)
        dst = os.path.join(OUT_DIR, os.path.splitext(name)[0] + ".gcs")
        if os.path.exists(dst):
            print("already saved, skipping: %s" % os.path.basename(dst))
            done.append(dst)
            continue
        try:
            sess.open_design(src)
            save_as(sess, dst)
            sess.ensure_idle()
            print("saved %s (%d bytes)" % (os.path.basename(dst),
                                           os.path.getsize(dst)))
            done.append(dst)
        except Exception as exc:
            failed.append((name, str(exc)[:160]))
            print("FAILED %s: %s" % (name, str(exc)[:160]))
            try:
                sess.ensure_idle()
            except Exception:
                pass

    print("\n%d saved, %d failed" % (len(done), len(failed)))
    print("GemCut left OPEN on purpose: it rewrites its config on exit.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
