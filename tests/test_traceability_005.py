"""Feature 005 documents. Gate 19.

The numbering across all features is checked once, in the 004 checker, which
globs every specification. What is particular to 005 is checked here: every
requirement reaches a task, the numbering continues from 004, the translations
name the same identifiers, and the two decisions most likely to be undone by a
later editor keep the words that make them requirements.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "specs" / "005-app"
DOCS = ROOT / "docs"

REQUIREMENT = re.compile(r"\b((?:FR|NR|PM|AC)-\d{3})\b")
DEFINITION = re.compile(
    r"^(?:- )?\*\*((?:FR|NR|PM|AC)-\d{3})\.?\*\*"
    r"|^\|\s*((?:FR|NR|PM|AC)-\d{3})\s*\|",
    re.MULTILINE,
)
IDENTIFIER = re.compile(
    r"\b((?:FR|NR|PM|AC)-\d{3}"
    r"|[ED]_[A-Z][A-Z0-9_]*[A-Z0-9]"
    r"|T(?:17|18|19)\d{2}"
    r"|K[1-9]"
    r"|C1[0-9]|C[1-9]"
    r"|Q1[0-9]|Q[1-9])\b"
)
FORBIDDEN_IN_SPEC = re.compile(
    r"\b(python|numpy|scipy|pandas|matplotlib|csv|json|dataframe|pytest|argparse"
    r"|fastapi|uvicorn|react|vite|typescript|pyinstaller|http)\b",
    re.IGNORECASE,
)

TRANSLATIONS = (
    (SPEC / "spec.md", DOCS / "005-spec.ko.md"),
    (SPEC / "data-model.md", DOCS / "005-data-model.ko.md"),
    (SPEC / "research.md", DOCS / "005-research.ko.md"),
)
# The research record is measured from a sample and is not published with the
# program; see the Licence section of the README. Where both halves of a pair
# are absent the pair drops out, and where only one is, the pair stays and the
# check below fails -- which is a deletion by mistake, not a deliberate one.
TRANSLATIONS = tuple(
    (english, korean)
    for english, korean in TRANSLATIONS
    if english.exists() or korean.exists()
)



def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _defined_in(text: str) -> set[str]:
    return {name for pair in DEFINITION.findall(text) for name in pair if name}


def test_every_requirement_is_reachable_from_a_task():
    defined = _defined_in(_read(SPEC / "spec.md"))
    scheduled = set(REQUIREMENT.findall(_read(SPEC / "tasks.md")))
    assert defined, "no requirements found in spec.md 005"
    missing = sorted(defined - scheduled)
    assert not missing, f"requirements with no task: {missing}"


def test_feature_005_continues_from_004():
    before = _defined_in(_read(ROOT / "specs" / "004-workflow" / "spec.md"))
    after = _defined_in(_read(SPEC / "spec.md"))
    for prefix in ("FR", "AC"):
        old = {int(n.split("-")[1]) for n in before if n.startswith(prefix)}
        new = {int(n.split("-")[1]) for n in after if n.startswith(prefix)}
        assert new and old
        assert min(new) == max(old) + 1, f"{prefix}: 005 starts at {min(new)}, 004 ends at {max(old)}"


def test_the_specification_names_no_technology():
    found = sorted(set(FORBIDDEN_IN_SPEC.findall(_read(SPEC / "spec.md"))))
    assert not found, f"spec.md 005 names technology: {found}"


def test_each_translation_refers_to_the_same_identifiers():
    for english, korean in TRANSLATIONS:
        source = set(IDENTIFIER.findall(_read(english)))
        translated = set(IDENTIFIER.findall(_read(korean)))
        assert source == translated, (
            f"{korean.name}: missing {sorted(source - translated)}, "
            f"extra {sorted(translated - source)}"
        )


def test_each_translation_states_that_the_english_is_normative():
    for _, korean in TRANSLATIONS:
        assert "정본" in _read(korean), f"{korean.name} does not name its source"


def test_every_server_code_is_in_the_data_model():
    from app.errors import APP_CODES

    data_model = _read(SPEC / "data-model.md")
    missing = [code for code in APP_CODES if f"`{code}`" not in data_model]
    assert not missing, f"codes the server raises and data model 005 omits: {missing}"


def test_the_page_defaults_to_the_rule_that_needs_no_outside_evidence():
    """FR-099. The held count is offered, and says what it needs."""
    spec = " ".join(_read(SPEC / "spec.md").split())
    assert "evidence from outside transport" in spec
    app = _read(ROOT / "frontend" / "src" / "App.tsx")
    assert "count: 'data'" in app


def test_the_command_line_stays_whole():
    """FR-107. The library must not come to depend on the page."""
    for path in (ROOT / "mbfit").rglob("*.py"):
        text = _read(path)
        assert "from app" not in text and "import app" not in text, path
        assert "fastapi" not in text, path
