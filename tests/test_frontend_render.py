"""FR-109 on the page, rendered and counted. Gate 19.

The type checker cannot see whether a value that is passed down is ever drawn:
a refit threaded through every component and never plotted type-checks
perfectly. So the components are rendered to static markup and the marks are
counted, by `frontend/src/render_check.tsx`.

This runs that check where the tools for it are present and skips where they
are not, in the same way the server tests skip without their dependencies. The
check is self-asserting: it exits non-zero and names what was missing.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


@pytest.mark.slow
def test_the_page_draws_the_refit_beside_the_procedures_answer():
    if not (FRONTEND / "node_modules").is_dir():
        pytest.skip("frontend dependencies not installed")
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm not on the path")
    done = subprocess.run([npm, "run", "--silent", "check:render"], cwd=FRONTEND,
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "render check passed" in done.stdout
