#!/usr/bin/env python
r"""
stage_viewer_work.py - stage gcs_viewer.py WITHOUT the parked render experiment.

    python scripts/stage_viewer_work.py

WHY THIS EXISTS
---------------
The working tree has carried an uncommitted raytracer since August 2026: a
Render button in `ViewerApp`, the `open_render_window` method behind it, and
the `self.material` the render window is handed.  Its own files
(`render_window.py`, `gem_render.py`, ...) are untracked on purpose.  None of
it may ride along into a viewer commit - a release that shipped the button
would ship a control that imports a module the repository does not contain.

WHY IT IS NOT THE OLD ONE
-------------------------
The first version of this lived only in a temp folder and worked by diffing
the file, then REVERSING every hunk that mentioned a marker word.  On
2026-11-13 that silently destroyed a day's work: the colour-set menu was
written into `ViewerApp.__init__` and `_load_data`, the same hunks that hold
`render_button` and `self.material`, so the whole hunk went back and the
commit kept only the half of the feature that lived elsewhere in the file.
The committed viewer had the ten colour sets as data and no way to choose
one; an exe was built from it and installed, and the CLI checks that were run
against it all passed, because the part that was missing was the window.

So this one does not work by hunks.  It removes NAMED, EXACT pieces of text,
and then refuses to stage anything unless the result still contains every
landmark the viewer is supposed to have.  A piece that cannot be found is a
hard error, not a quiet skip: the render experiment changes shape over time,
and the correct response to "I no longer recognise this" is to stop.

AFTER STAGING, VERIFY THE COMMIT, NOT THE WORKING TREE
------------------------------------------------------
The lesson of 2026-11-13 is that a suite run against the working tree says
nothing about what was committed.  `scripts/check_commit.py` checks out the
commit into a throwaway worktree and runs both suites there.  Do that before
building an exe from it.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = "gcs_viewer.py"
SUITE = "test_gui.py"

# Exact text the render experiment adds, each with a name for the report.
# Trailing blank lines are part of the piece: removing a method must not
# leave the two blank lines that separated it from its neighbour.
PIECES = [
    ("the Render button", '''
        # the flat panels say what the design IS; the render says what it will
        # look like cut, which is a different question and a different window
        self.render_button = tk.Button(
            controls, text="Render", command=self.open_render_window,
            bg="#33333c", fg="#c8c8d0", activebackground="#3f3f4a",
            activeforeground="#ffffff", bd=0, padx=12, pady=2,
            font=("Segoe UI", 10), takefocus=0)
        self.render_button.pack(side="left", padx=(0, 12))
''', ""),
    ("open_render_window()", '''    def open_render_window(self):
        """Open the raytraced render on this design.

        Imported here rather than at the top: the render window pulls in the
        renderer's plumbing, and the viewer's first job is to put a design on
        screen quickly for somebody arrowing through a folder.  Nobody should
        pay for a renderer they did not ask for.
        """
        try:
            import render_window
        except ImportError as exc:
            self.status.config(text="render window unavailable: %s" % exc)
            return
        win = render_window.RenderWindow(self.root, self.path,
                                         facets=self.facets, info=self.info,
                                         colour=self.material)
        win.focus_set()

''', ""),
    ("the material handed to the render window",
     '        self.material = material           # index, dispersion, density...\n',
     ""),
]

# The window suite grew a check for the Render button too.  Committing that
# while holding the button itself back leaves a suite that cannot pass on the
# tree it was committed with - which is how check_commit.py earned its keep
# ten minutes after it was written.
SUITE_PIECES = [
    ("the Render button's window check",
     '''            check("window: Render sits to the left of the checkbox",
                  app.render_button.winfo_exists() and
                  app.render_button.cget("text") == "Render" and
                  list(app.render_button.master.pack_slaves()).index(
                      app.render_button) <
                  list(app.tier_check.master.pack_slaves()).index(
                      app.tier_check),
                  [w.cget("text") for w in app.render_button.master.pack_slaves()])
''', ""),
]

SUITE_MUST_KEEP = [
    'check("sets: the chooser is above the stone"',
    'check("sets: and at the right edge"',
    "menu = app.tier_menu_items",
    'check("sets: and the choice is written down at once"',
]

# Landmarks that must SURVIVE.  Each one is a thing the render experiment
# sits next to, which is exactly how the old helper came to eat them.
MUST_KEEP = [
    "self.tier_menu = tk.Menubutton(",         # the colour-set chooser
    "self.tier_menu_items = tk.Menu(",
    "def _choose_tier_set(self, label):",
    "def tier_set_brief(label):",
    "self.palette, self.tier_short = tier_palette_set(facets,",
    'text="Color-code tiers"',                 # US spelling, as the suite asks
    "def tier_palette_set(facets, set_id):",
    "def remembered_tier_set():",
]

# Nothing from the experiment may remain.
MUST_GO = ["render_button", "open_render_window", "self.material",
           "render_window"]


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=REPO, text=True,
                          capture_output=True)


def stage_one(name, pieces, must_keep, must_go):
    """Write the file without its render pieces, git add it, put it back."""
    full = os.path.join(REPO, name)
    raw = io.open(full, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    body = raw.replace("\r\n", "\n")

    staged = body
    for what, find, repl in pieces:
        n = staged.count(find)
        if n != 1:
            sys.exit("STOP: %s appears %d times in %s, expected once.\n"
                     "The render experiment has changed shape - read it and "
                     "update the piece rather than letting this guess."
                     % (what, n, name))
        staged = staged.replace(find, repl)
        print("  held back from %s: %s" % (name, what))

    missing = [k for k in must_keep if k not in staged]
    left = [k for k in must_go if k in staged]
    if missing or left:
        sys.exit("STOP: nothing staged from %s.\n  lost: %s\n  survived: %s"
                 % (name, missing or "-", left or "-"))

    # a Python file that does not compile is not a commit
    try:
        compile(staged, name, "exec")
    except SyntaxError as exc:
        sys.exit("STOP: the staged %s does not compile: %s" % (name, exc))

    backup = full + ".worktree"
    shutil.copy2(full, backup)
    try:
        io.open(full, "w", encoding="utf-8",
                newline="\r\n" if crlf else "\n").write(staged)
        r = git("add", "--", name)
        if r.returncode:
            sys.exit("git add failed:\n" + r.stderr)
    finally:
        shutil.copy2(backup, full)
        os.remove(backup)
    return len(body.splitlines()) - len(staged.splitlines())


def main():
    kept = stage_one(FILE, PIECES, MUST_KEEP, MUST_GO)
    kept += stage_one(SUITE, SUITE_PIECES, SUITE_MUST_KEEP, MUST_GO)
    print("staged without the render experiment (%d lines held back);"
          " the working tree still has it" % kept)
    print("now verify the COMMIT, not the working tree:"
          "  python scripts/check_commit.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
