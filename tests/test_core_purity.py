"""Constitution Article I, enforced.

Every module under `mbfit/core/` may import numpy and the standard library,
and nothing else. No pandas, no scipy, no matplotlib, no file access, no
argument parsing.

A rule you cannot avoid keeping is the only kind that is really a rule. This
test parses the imports rather than trusting a reading of them.
"""

from __future__ import annotations

import ast
import pathlib
import sys

CORE = pathlib.Path(__file__).resolve().parent.parent / "mbfit" / "core"
ALLOWED_THIRD_PARTY = {"numpy"}


def _core_modules():
    return sorted(CORE.glob("*.py"))


def _imported_roots(path: pathlib.Path):
    """Top-level names imported by a module, excluding relative imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: inside the core, allowed
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_core_directory_is_not_empty():
    assert _core_modules(), "no modules found under mbfit/core"


def test_core_imports_only_numpy_and_the_standard_library():
    offences = []
    for path in _core_modules():
        for root in sorted(_imported_roots(path)):
            if root in ALLOWED_THIRD_PARTY:
                continue
            if root in sys.stdlib_module_names:
                continue
            offences.append(f"{path.name} imports {root}")
    assert not offences, (
        "Article I: mbfit/core may import only numpy and the standard library. "
        + "; ".join(offences)
    )


def test_the_check_would_catch_a_violation():
    """The enforcement itself is tested, on source that is never imported.

    Without this, a bug in the parser above would make Article I pass
    vacuously for the rest of the project's life.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        offender = pathlib.Path(directory) / "offender.py"
        offender.write_text("import pandas as pd\nfrom scipy import optimize\n", encoding="utf-8")
        roots = _imported_roots(offender)
    assert "pandas" in roots and "scipy" in roots
    assert not (roots & ALLOWED_THIRD_PARTY)
