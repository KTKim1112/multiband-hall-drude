"""Entry script for the frozen build. FR-106.

PyInstaller runs its entry point as `__main__`, which has no parent package, so
`app/desktop.py` cannot be the entry point: its `from .main import app` fails,
and fails during analysis too, after which nothing beyond that import is
bundled. The sibling project's first build came out at 11 MB with neither numpy
nor scipy in it. This file turns the relative import into an absolute one and
holds no logic, so the executable and `python -m app.desktop` cannot diverge.
"""

import multiprocessing
import sys

from app.desktop import main

if __name__ == "__main__":
    # A frozen program that ever starts a process re-enters here in the child;
    # this makes that child do its work and exit instead of starting a server.
    multiprocessing.freeze_support()
    sys.exit(main())
