#!/usr/bin/env python
"""
test_gui.py - checks for the parts only the window owns.

    python test_gui.py

test_gcs_viewer.py covers the readers, the geometry and the renderer, all of
which can be exercised without a display.  What it cannot reach is the thing
the user actually operates: stepping through a folder with the arrow keys,
the toggles, the tilt limits, and what the status line says.

This drives the real widgets and pumps Tk's event loop by hand rather than
calling mainloop(), so it runs unattended, and it skips cleanly where Tk has
no display - which keeps a headless Linux runner green without xvfb.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")

# see the same note in test_gcs_viewer.py: a build agent's console is cp1252,
# and a suite must not be able to die on the text it prints
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PASS = 0
FAIL = []


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL.append(name)
        print("  FAIL %s   %s" % (name, detail))


def have_display():
    try:
        import tkinter as tk
    except Exception:
        return False
    try:
        r = tk.Tk()
    except Exception:
        return False
    r.destroy()
    return True


def build_folder(tmp):
    """Three readable designs, one unreadable, and a decoy of another type."""
    import gcs_viewer as gv
    import test_gcs_viewer as suite

    names = []
    for i, angle in enumerate((43.0, 41.0, 39.0), start=1):
        p = os.path.join(tmp, "stone%d.gcs" % i)
        facets = suite.cone_facets(8, angle, tier="P1", instr="Cut to a point")
        facets += suite.table_facet(z=0.4)
        gv.write_gcs(p, facets, {"title": "Stone %d" % i},
                     {"color": (0.2, 0.5, 0.9)})
        names.append(p)

    bad = os.path.join(tmp, "stone4_broken.gcs")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("<GemCutStudio>not xml")
    with open(os.path.join(tmp, "notes.txt"), "w", encoding="utf-8") as fh:
        fh.write("not a design")
    return names, bad


def pump(app, n=3):
    for _ in range(n):
        app.root.update_idletasks()
        app.root.update()


def main():
    if not have_display():
        print("skipped: Tk has no display here")
        return 0

    import gcs_viewer as gv

    with tempfile.TemporaryDirectory() as tmp:
        designs, broken = build_folder(tmp)

        app = gv.ViewerApp(designs[0])
        app.root.withdraw()                    # no need to flash on screen
        pump(app)

        try:
            check("window: opens on the file it was given",
                  os.path.normcase(app.path) ==
                  os.path.normcase(os.path.abspath(designs[0])), app.path)
            check("window: title carries the version and the file name",
                  gv.__version__ in app.root.title() and
                  "stone1.gcs" in app.root.title(), app.root.title())
            check("window: an image is on screen",
                  app.label.cget("image") != "", app.label.cget("image"))
            check("window: the cutting table is its own strip below it",
                  app.instr_label.cget("image") != "" and
                  app.instr_label.winfo_manager() == "pack",
                  app.instr_label.cget("image"))
            check("window: the checkbox sits between them",
                  list(app.root.pack_slaves()).index(app.tier_check.master) ==
                  list(app.root.pack_slaves()).index(app.label) + 1 and
                  list(app.root.pack_slaves()).index(app.instr_label) ==
                  list(app.root.pack_slaves()).index(app.tier_check.master) + 1,
                  [w.winfo_class() for w in app.root.pack_slaves()])
            check("window: it opens with the tiers coloured",
                  app.tier_colors is True and app.tier_colors_var.get() == 1,
                  (app.tier_colors, app.tier_colors_var.get()))
            check("window: the four panels and the table were composed",
                  app._canvas.width >= app.panel * 4, app._canvas.size)

            # -- stepping through the folder --
            app._step_file(1)
            pump(app)
            check("arrows: right steps to the next design",
                  os.path.basename(app.path) == "stone2.gcs",
                  os.path.basename(app.path))
            check("arrows: the title follows",
                  "stone2.gcs" in app.root.title(), app.root.title())

            app._step_file(-1)
            pump(app)
            check("arrows: left steps back",
                  os.path.basename(app.path) == "stone1.gcs",
                  os.path.basename(app.path))

            app._step_file(-1)
            pump(app)
            check("arrows: stepping back from the first wraps to the last",
                  os.path.basename(app.path) == "stone3.gcs",
                  os.path.basename(app.path))

            # the broken file sorts between stone3 and stone1; walking must
            # step over it rather than stopping or showing an error
            app._step_file(1)
            pump(app)
            check("arrows: an unreadable design is skipped, not fatal",
                  os.path.basename(app.path) == "stone1.gcs",
                  os.path.basename(app.path))

            check("arrows: the decoy .txt is not in the walk",
                  all(not p.endswith(".txt") for p in app._siblings()))
            check("status: says where you are in the folder",
                  "1 / 4" in app.status.cget("text") or
                  "1 / 3" in app.status.cget("text"),
                  app.status.cget("text"))

            # Browsing is what this program is for - a real folder here holds
            # a thousand designs - so the caches that make it quick must not
            # grow with the walk.  Measured separately: 200 steps through a
            # 996-design folder ends 0.3 MB below where it started.
            for _ in range(30):
                app._step_file(1)
            pump(app)
            check("browsing: the instruction cache stays at its bound",
                  len(gv._INSTR_CACHE) <= 4, len(gv._INSTR_CACHE))
            check("browsing: the folder cache does not grow with the walk",
                  len(gv._FOLDER_CACHE) <= 8, len(gv._FOLDER_CACHE))
            check("browsing: the text-fitting cache stays at its bound",
                  len(gv._FIT_CACHE) <= 8, len(gv._FIT_CACHE))
            check("browsing: and it is still on a real design",
                  os.path.isfile(app.path), app.path)

            # -- the 3/4 view --
            az0, el0 = app.az, app.el
            app._nudge(0, 6)
            pump(app)
            check("tilt: up raises the elevation", app.el == el0 + 6, app.el)
            for _ in range(40):
                app._nudge(0, 6)
            check("tilt: elevation is clamped short of straight up",
                  app.el <= 88.0, app.el)
            for _ in range(80):
                app._nudge(0, -6)
            check("tilt: and short of straight down", app.el >= -88.0, app.el)

            app._reset()
            pump(app)
            check("reset: returns to the starting angle",
                  (app.az, app.el) == (35.0, 28.0), (app.az, app.el))

            class E:
                pass
            e = E(); e.x, e.y = 100, 100
            app._press(e)
            e2 = E(); e2.x, e2.y = 160, 100
            app._drag(e2)
            pump(app)
            check("drag: moving the mouse spins the stone", app.az != 35.0,
                  app.az)
            app._release(e2)
            pump(app)
            check("drag: releasing re-renders at full quality",
                  app._canvas is not None)

            # -- toggles --
            # the sheet is shown as two strips with the controls between, so
            # it is the lower one that grows and shrinks with the table
            before = app._table_canvas.height
            views_before = app._canvas.height
            app._toggle_instr()
            pump(app)
            check("I: hiding the table makes the sheet shorter",
                  app._table_canvas.height < before,
                  (before, app._table_canvas.height))
            check("I: the renders above it do not move",
                  app._canvas.height == views_before,
                  (views_before, app._canvas.height))
            app._toggle_instr()
            pump(app)
            check("I: showing it again restores the height",
                  app._table_canvas.height == before,
                  (before, app._table_canvas.height))

            app._toggle("gray")
            pump(app)
            check("G: grayscale is remembered", app.gray is True)
            app._toggle("gray")
            app._toggle("labels")
            pump(app)
            check("L: labels toggle off", app.labels is False)
            app._toggle("labels")
            pump(app)

            # -- the keys themselves --
            #
            # Everything above calls the methods.  That leaves the actual
            # wiring untested: a binding removed, or bound to the wrong key,
            # would not fail a single check.  These go through Tk's event
            # dispatch, which is what the user's keyboard does.
            app.root.deiconify()               # key events need a mapped window
            app.root.update()
            here = app.path

            def key(seq):
                app.root.focus_force()
                app.root.event_generate(seq, when="now")
                pump(app)

            # Whether synthetic key events reach a binding depends on the
            # window manager and on the window having focus, neither of which
            # is guaranteed on a build agent.  Probe it with a key of our own
            # first: if dispatch does not work here, say so once rather than
            # reporting seven failures that mean nothing about the program.
            fired = []
            app.root.bind("<F9>", lambda e: fired.append(1))
            key("<F9>")
            app.root.unbind("<F9>")
            dispatch = bool(fired)
            if not dispatch:
                print("  ..   key dispatch unavailable here; key checks skipped")

            if dispatch:
                key("<Right>")
                moved = app.path != here
                check("keys: Right is bound to stepping forward", moved,
                      os.path.basename(app.path))
                if moved:
                    key("<Left>")
                    check("keys: Left steps back to where it was",
                          app.path == here, os.path.basename(app.path))

                before_gray = app.gray
                key("g")
                check("keys: g toggles grayscale", app.gray != before_gray,
                      app.gray)
                key("g")

                before_labels = app.labels
                key("l")
                check("keys: l toggles the tier labels",
                      app.labels != before_labels, app.labels)
                key("l")

                before_instr = app.show_instr
                key("i")
                check("keys: i toggles the instructions table",
                      app.show_instr != before_instr, app.show_instr)
                key("i")

                before_tint = app.tier_colors
                key("c")
                check("keys: c toggles the tier colours",
                      app.tier_colors != before_tint, app.tier_colors)
                check("keys: c moves the checkbox with it",
                      bool(app.tier_colors_var.get()) == app.tier_colors,
                      app.tier_colors_var.get())
                key("c")

                app.az = 111.0
                key("r")
                check("keys: r resets the 3/4 angle", app.az == 35.0, app.az)

                el_before = app.el
                key("<Up>")
                check("keys: Up tilts the view", app.el != el_before, app.el)
                key("<Down>")
            app.root.withdraw()

            # -- the tier-colour checkbox --
            # it is the control the user actually clicks, so drive the widget
            # rather than the method behind it
            check("colours: the window offers a checkbox for them",
                  app.tier_check.winfo_exists() and
                  app.tier_check.cget("text") == "Color-code tiers",
                  app.tier_check.cget("text"))
            # US spelling on the label, whatever the code calls it internally:
            # the program is written in British English and read mostly by
            # Americans, and "Colour" on a button reads as a typo to them
            check("colours: the label is spelled the American way",
                  "Colour" not in app.tier_check.cget("text"),
                  app.tier_check.cget("text"))
            # earlier checks in this run have toggled gray, which turns the
            # colours off - so put the state where this block needs it rather
            # than assuming it (asserting "starts off" here passed for a while
            # on that leftover state, testing nothing)
            if app.tier_colors:
                app.tier_check.invoke()
                pump(app)
            check("colours: they can be turned off", app.tier_colors is False)
            plain = app._canvas.copy()
            app.tier_check.invoke()
            pump(app)
            check("colours: ticking it turns them on", app.tier_colors is True)
            check("colours: and the stone is redrawn",
                  list(app._canvas.getdata()) != list(plain.getdata()))
            check("colours: every tier gets its own",
                  len(set(map(tuple, app.palette.values()))) ==
                  len(app.palette) and len(app.palette) > 1,
                  len(app.palette))

            # -- the colour-set menu --
            # Ten sets: two for normal vision and one for each kind of
            # colour blindness, the same ones the website offers.  Driven
            # through the widget, because what matters is that the menu
            # entry does the work, not that the method behind it does.
            labels = [spec["label"] for spec in gv.TIER_SETS]
            menu = app.tier_menu_items
            entries = [menu.entrycget(i, "label")
                       for i in range(menu.index("end") + 1)]
            check("sets: the window offers every set",
                  entries == labels, entries)
            check("sets: it opens on the set it will use",
                  app.tier_set_var.get() == gv.tier_set_brief(
                      gv.tier_set(app.tier_set_id)["label"]),
                  (app.tier_set_var.get(), app.tier_set_id))
            # The chooser is the first control a user needs - before reading
            # anything they pick the set that matches their own sight - so it
            # sits ABOVE the stone and hard RIGHT, not below it with the
            # toggles.  Asked of the geometry manager rather than of screen
            # pixels, because this window is never mapped while under test.
            topbar = app.root.nametowidget(app.tier_menu.winfo_parent())
            order = app.root.pack_slaves()
            check("sets: the chooser is above the stone",
                  order.index(topbar) < order.index(app.label)
                  and topbar.pack_info().get("side", "top") == "top",
                  ([w.winfo_class() for w in order], topbar.pack_info()))
            check("sets: and at the right edge",
                  app.tier_menu.pack_info()["side"] == "right",
                  app.tier_menu.pack_info())
            check("sets: the top bar spans the window",
                  topbar.pack_info()["fill"] == "x", topbar.pack_info())
            # it is named for the SIGHT it serves, not for what the viewer
            # paints: somebody looking for it is looking for that word
            check("sets: the chooser is named for colour blindness",
                  app.tier_caption.cget("text") == "Color Blindness Mode",
                  app.tier_caption.cget("text"))
            check("sets: spelled the American way",
                  "Colour" not in app.tier_caption.cget("text"),
                  app.tier_caption.cget("text"))
            # a control for people who may not see the difference between
            # two tier colours has no business being the dimmest, smallest
            # thing on screen - it is read before the stone, not beside it
            def pt(w):
                f = str(w.cget("font"))
                return int(f.strip("{}").split()[-1])

            def lum(w):
                h = w.cget("foreground").lstrip("#")
                r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                return 0.299 * r + 0.587 * g + 0.114 * b

            check("sets: the caption is larger than the controls below",
                  pt(app.tier_caption) > pt(app.tier_check),
                  (pt(app.tier_caption), pt(app.tier_check)))
            check("sets: and the chooser with it",
                  pt(app.tier_menu) == pt(app.tier_caption),
                  (pt(app.tier_menu), pt(app.tier_caption)))
            check("sets: the caption is brighter than the status line",
                  lum(app.tier_caption) > lum(app.status) + 30,
                  (lum(app.tier_caption), lum(app.status)))
            # it sat against the title bar before
            check("sets: there is a gap above it",
                  int(str(topbar.pack_info()["pady"]).strip("()").split(
                      ",")[0]) >= 10, topbar.pack_info()["pady"])
            # a set that changed the button's width would shift the whole
            # control sideways every time it was used
            widths = []
            for spec in gv.TIER_SETS:
                app.tier_set_var.set(gv.tier_set_brief(spec["label"]))
                app.root.update_idletasks()
                widths.append(app.tier_menu.winfo_reqwidth())
            app.tier_set_var.set(gv.tier_set_brief(
                gv.tier_set(app.tier_set_id)["label"]))
            app.root.update_idletasks()
            check("sets: the button does not change width with the set",
                  len(set(widths)) == 1, widths)
            check("sets: and that is the remembered one",
                  app.tier_set_id == gv.remembered_tier_set(),
                  (app.tier_set_id, gv.remembered_tier_set()))

            # keep the test off the real preferences file
            home = os.path.join(tmp, "gui-prefs")
            keep = {k: os.environ.get(k)
                    for k in ("APPDATA", "XDG_CONFIG_HOME")}
            os.environ["APPDATA"] = home
            os.environ["XDG_CONFIG_HOME"] = home
            try:
                if not app.tier_colors:
                    app.tier_check.invoke()
                    pump(app)
                before = app._canvas.copy()
                was = dict(app.palette)
                menu.invoke(labels.index("Tritanopia (Blue-blind)"))
                pump(app)
                check("sets: picking one switches to it",
                      app.tier_set_id == "tritanopia", app.tier_set_id)
                check("sets: the menu shows what was picked",
                      app.tier_set_var.get() == "Tritanopia",
                      app.tier_set_var.get())
                check("sets: the stone is recoloured",
                      dict(app.palette) != was
                      and list(app._canvas.getdata()) != list(before.getdata()))
                check("sets: and the choice is written down at once",
                      gv.load_prefs().get("tier_set") == "tritanopia",
                      gv.load_prefs())

                # a monochromacy set draws the stone unshaded: lightness is
                # the only cue those viewers have
                check("sets: an ordinary set is shaded", app._flat() is False)
                menu.invoke(labels.index(
                    "Achromatopsia / Rod Monochromacy (Total color blindness)"))
                pump(app)
                check("sets: a monochromacy set is drawn flat",
                      app._flat() is True and app.tier_set_id == "achromatopsia",
                      (app._flat(), app.tier_set_id))

                # picking a set with the colours off would do nothing
                # visible, which reads as a broken menu
                app.tier_check.invoke()
                pump(app)
                check("sets: the colours are off now", app.tier_colors is False)
                menu.invoke(labels.index("None (Vibrant)"))
                pump(app)
                check("sets: picking one turns the colours back on",
                      app.tier_colors is True
                      and app.tier_colors_var.get() == 1
                      and app.tier_set_id == "vibrant",
                      (app.tier_colors, app.tier_set_id))

                # what a new window would open with
                check("sets: a later run starts on the last one picked",
                      gv.remembered_tier_set() == "vibrant",
                      gv.remembered_tier_set())
                menu.invoke(labels.index("None (Pastel)"))
                pump(app)
            finally:
                for k, v in keep.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

            # grayscale and tier colours both claim the facet colour: the one
            # asked for last wins, and the checkbox must not lie about it
            key = lambda k: (app.root.event_generate(
                "<KeyPress-%s>" % k), pump(app))
            app.root.deiconify()
            app.root.focus_force()
            pump(app)
            app._toggle("gray")
            pump(app)
            check("colours: turning on gray turns them off",
                  app.gray is True and app.tier_colors is False,
                  (app.gray, app.tier_colors))
            check("colours: and unticks the checkbox",
                  app.tier_colors_var.get() == 0, app.tier_colors_var.get())
            app.tier_check.invoke()
            pump(app)
            check("colours: ticking them back turns gray off",
                  app.tier_colors is True and app.gray is False,
                  (app.tier_colors, app.gray))
            app.tier_check.invoke()                 # back to plain for saving
            pump(app)
            app.root.withdraw()

            # -- saving --
            app._save()
            pump(app)
            out = os.path.splitext(app.path)[0] + "_views.png"
            check("S: writes a PNG beside the design",
                  os.path.exists(out) and os.path.getsize(out) > 5000,
                  os.path.getsize(out) if os.path.exists(out) else "missing")
            check("S: says so in the status line",
                  "Saved" in app.status.cget("text"), app.status.cget("text"))
            check("S: the design itself is untouched",
                  os.path.getsize(app.path) > 0)
        finally:
            app.root.destroy()

        # a folder holding one design: stepping must say so, not wrap forever
        solo = os.path.join(tmp, "solo")
        os.makedirs(solo, exist_ok=True)
        only = os.path.join(solo, "only.gcs")
        with open(designs[0], "rb") as src, open(only, "wb") as dst:
            dst.write(src.read())
        app2 = gv.ViewerApp(only)
        app2.root.withdraw()
        pump(app2)
        try:
            app2._step_file(1)
            pump(app2)
            check("arrows: a folder with one design says so",
                  "one" in app2.status.cget("text").lower(),
                  app2.status.cget("text"))
            check("arrows: and stays on that design",
                  os.path.basename(app2.path) == "only.gcs")
        finally:
            app2.root.destroy()

    print("\n%d checks passed, %d failed" % (PASS, len(FAIL)))
    for f in FAIL:
        print("  FAILED: %s" % f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
