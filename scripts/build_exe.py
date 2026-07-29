"""
build_exe.py - freeze the GCS Viewer into a single-file Windows .exe.

    python scripts/build_exe.py             # build, then install over the
                                            # live GCSViewer.exe at the repo root
    python scripts/build_exe.py --clean     # wipe build/ and dist/ first
    python scripts/build_exe.py --onedir    # folder build instead of onefile
    python scripts/build_exe.py --no-install  # leave dist/ alone, don't copy

Produces dist/GCSViewer.exe and copies it to <repo>/GCSViewer.exe, which is
the path the .gcs file association points at - keeping the same name and path
is what preserves the association across a rebuild.

Needs PyInstaller:  pip install pyinstaller

Note: every PyInstaller path (spec, work, dist) is kept inside this project,
which lives on D:.  Building with the spec file on C: has failed on this
machine, so do not "helpfully" move it back to a temp directory.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "GCSViewer"
ENTRY = os.path.join(HERE, "gcs_viewer.py")


def main():
    if "--clean" in sys.argv:
        for d in ("build", "dist"):
            p = os.path.join(HERE, d)
            if os.path.isdir(p):
                shutil.rmtree(p)
                print("removed %s" % p)

    onedir = "--onedir" in sys.argv
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir" if onedir else "--onefile",
        "--windowed",                 # Explorer double-click, no console flash
        "--name", NAME,
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        # numpy and Pillow are genuine dependencies; the rest is dead weight
        # PyInstaller otherwise hoovers up through transitive imports
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
        ENTRY,
    ]
    icon = os.path.join(HERE, "docs", "gcsviewer.ico")
    if os.path.exists(icon):
        cmd[cmd.index("--name"):cmd.index("--name")] = ["--icon", icon]

    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        sys.exit("PyInstaller failed (%d)" % r.returncode)

    built = os.path.join(HERE, "dist", NAME, NAME + ".exe") if onedir \
        else os.path.join(HERE, "dist", NAME + ".exe")
    print("\nbuilt %s (%.1f MB)" % (built, os.path.getsize(built) / 1048576.))

    if not onedir and "--no-install" not in sys.argv:
        live = os.path.join(HERE, NAME + ".exe")
        try:
            shutil.copy2(built, live)
            print("installed -> %s" % live)
        except PermissionError:
            print("could not overwrite %s - is the viewer still open?" % live)
            sys.exit(1)

    print('self-test it with:  "%s" --selftest report.txt' % built)


if __name__ == "__main__":
    main()
