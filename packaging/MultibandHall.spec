# PyInstaller build of the Windows folder. FR-106.
#
# Run it through `packaging/build.ps1`: the build needs `app/static/`, which the
# frontend build produces and nothing here does.
#
# One folder, not one file. Measured in the sibling project: one file unpacks
# its whole payload into a temporary directory on every launch, starts more than
# twice as slowly, and has the shape antivirus heuristics call a dropper.

import pathlib

from PyInstaller.utils.hooks import collect_submodules

ROOT = pathlib.Path(SPECPATH).resolve().parent

# `app.resources.root()` returns the extraction directory when frozen, and the
# page is laid out under it exactly as it sits beside the `app` package.
datas = [(str(ROOT / "app" / "static"), "static")]

# uvicorn imports its loop, protocol and lifespan implementations from strings
# at startup, which static analysis cannot see.
hiddenimports = collect_submodules("uvicorn")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Nothing on the page's path imports these. matplotlib draws the figures of
    # the command line's declared-carrier run only; pandas is not excluded,
    # because the library reads tables with it.
    excludes=[
        "matplotlib",
        "tkinter",
        "IPython",
        "pytest",
        "PyInstaller",
        "notebook",
        "jupyter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MultibandHall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # No UPX: a useful saving in size, and one of the strongest signals
    # antivirus heuristics use on a file that arrives by email.
    upx=False,
    # The console window is the stop button. Without it a forgotten server runs
    # until the next reboot with nothing on screen to say so.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MultibandHall",
)
