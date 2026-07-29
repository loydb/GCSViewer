"""
build_exe.py - freeze the GCS Viewer into a single-file Windows .exe.

    python scripts/build_exe.py             # build, then update the copy
                                            # Windows actually launches
    python scripts/build_exe.py --clean     # wipe build/ and dist/ first
    python scripts/build_exe.py --onedir    # folder build instead of onefile
    python scripts/build_exe.py --no-install  # leave dist/ alone, don't copy

"Install" means the copy the .gcs association points at, which is read from
the registry rather than assumed.  Editing the source and rebuilding into a
binary nobody launches is precisely how this project once shipped an exe four
weeks behind its own source, and moving an install to a different folder or
a different distribution shape re-creates that trap silently.  If the
registered copy is a folder build and this is a --onefile build, or the
reverse, the shapes do not match and it says so instead of writing a broken
mixture.

Needs PyInstaller:  pip install pyinstaller

Note: every PyInstaller path (spec, work, dist) is kept inside this project,
which lives on D:.  Building with the spec file on C: has failed on this
machine, so do not "helpfully" move it back to a temp directory.
"""

import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "GCSViewer"
ENTRY = os.path.join(HERE, "gcs_viewer.py")
PROGID_CMD = r"Software\Classes\GcsViewer.Stone\shell\open\command"


def exe_from_command(cmd):
    """Pull the program out of a registered shell-open command string.

    The value looks like  "D:\\Tools\\GCSViewer\\GCSViewer.exe" "%1"  - quoted
    because the path contains spaces, which every install location here does.
    An unquoted form is accepted too, since a hand-edited key may not quote.
    """
    if not cmd:
        return None
    cmd = cmd.strip()
    m = re.match(r'"([^"]+)"', cmd)
    if m:
        return m.group(1)
    return cmd.split(" %")[0].strip() or None


def registered_exe():
    """Where a double-click actually goes, or None if nothing is registered."""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROGID_CMD) as k:
            value, _ = winreg.QueryValueEx(k, None)
    except (ImportError, OSError):
        return None
    path = exe_from_command(value)
    return path if path and os.path.exists(path) else None


def is_folder_build(exe_path):
    """A onedir build keeps its libraries in an _internal folder beside it."""
    return os.path.isdir(os.path.join(os.path.dirname(exe_path), "_internal"))


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

    if "--no-install" not in sys.argv:
        install(built, onedir)

    print('self-test it with:  "%s" --selftest report.txt' % built)


def install(built, onedir):
    """Update the copy Windows launches, or say why it was not touched."""
    live = registered_exe()
    if live is None:
        live = os.path.join(HERE, NAME + ".exe")
        print("nothing registered for .gcs - installing to %s" % live)
    elif is_folder_build(live) != onedir:
        want = "--onedir" if is_folder_build(live) else "--onefile"
        print("\nNOT installed. The registered copy is at\n    %s\nand is a "
              "%s build, but this is a %s build."
              % (live, "folder" if is_folder_build(live) else "single-file",
                 "folder" if onedir else "single-file"))
        print("Rebuild with %s, or re-run Install-GcsViewer.ps1 from wherever "
              "you want the association to point." % want)
        return

    try:
        if onedir:
            # replace the contents rather than the folder itself: the folder
            # may be open in Explorer, and _internal holds a thousand files
            # that must not be left mixed between two builds
            dest = os.path.dirname(live)
            internal = os.path.join(dest, "_internal")
            if os.path.isdir(internal):
                shutil.rmtree(internal)
            src = os.path.dirname(built)
            for name in os.listdir(src):
                s = os.path.join(src, name)
                d = os.path.join(dest, name)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            print("installed -> %s (folder build)" % dest)
        else:
            shutil.copy2(built, live)
            print("installed -> %s" % live)
    except PermissionError:
        print("could not overwrite %s - is the viewer still open?" % live)
        sys.exit(1)


if __name__ == "__main__":
    main()
