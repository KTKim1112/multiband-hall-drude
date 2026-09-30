"""Where the built page is, from source or frozen.

Frozen, PyInstaller unpacks data files under `sys._MEIPASS`, laid out as they
are beside this package, so one function covers both cases. Not in `mbfit/`:
it knows about a packaging tool, which the library does not.
"""

from __future__ import annotations

import os
import pathlib
import sys


def state() -> pathlib.Path:
    """Where the program remembers one run's worth of nothing important.

    Not beside the executable: the folder it was unpacked into may be read
    only, on a share, or inside a temporary directory. Nothing here is a
    measurement, so losing it costs one browser window.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    home = pathlib.Path(base) if base else pathlib.Path.home() / ".local" / "state"
    return home / "MultibandHall"


def root() -> pathlib.Path:
    """The directory holding `static/`."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled is not None:
        return pathlib.Path(bundled)
    return pathlib.Path(__file__).resolve().parent


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
