"""Feature 004 documents, and the numbering across all four. Gate 15.

The append-only rule spans four specifications now, so the check that
requirement numbers have no gaps and no reuse looks at all of them at once.
Feature 004 adds no diagnostic code -- what the workflow reports about itself is
a column, not an event -- so the two checks on diagnostic codes that feature 003
carries have no counterpart here.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = sorted((ROOT / "specs").glob("*/spec.md"))
SPEC = ROOT / "specs" / "004-workflow"
DOCS = ROOT / "docs"

REQUIREMENT = re.compile(r"\b((?:FR|NR|PM|AC)-\d{3})\b")
DIAGNOSTIC = re.compile(r"\b(D_[A-Z][A-Z0-9_]*[A-Z0-9])\b")
DEFINITION = re.compile(
    r"^(?:- )?\*\*((?:FR|NR|PM|AC)-\d{3})\.?\*\*"
    r"|^\|\s*((?:FR|NR|PM|AC)-\d{3})\s*\|",
    re.MULTILINE,
)
IDENTIFIER = re.compile(
    r"\b((?:FR|NR|PM|AC)-\d{3}"
    r"|[ED]_[A-Z][A-Z0-9_]*[A-Z0-9]"
    r"|T(?:14|15)\d{2}"
    r"|K[1-9]"
    r"|C1[0-9]|C[1-9]"
    r"|Q1[0-9]|Q[1-9])\b"
)
FORBIDDEN_IN_SPEC = re.compile(
    r"\b(python|numpy|scipy|pandas|matplotlib|csv|json|dataframe|pytest|argparse)\b",
    re.IGNORECASE,
)

TRANSLATIONS = (
    (SPEC / "spec.md", DOCS / "004-spec.ko.md"),
    (SPEC / "research.md", DOCS / "004-research.ko.md"),
    (SPEC / "data-model.md", DOCS / "004-data-model.ko.md"),
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
    assert defined, "no requirements found in spec.md 004"
    missing = sorted(defined - scheduled)
    assert not missing, f"requirements with no task: {missing}"


def test_the_whole_project_has_no_gaps_and_no_reuse():
    """Append-only numbering, across every feature there is."""
    seen: dict[str, str] = {}
    for path in SPECS:
        for name in _defined_in(_read(path)):
            assert name not in seen, (
                f"{name} defined in both {seen[name]} and {path.parent.name}"
            )
            seen[name] = path.parent.name

    for prefix in ("FR", "NR", "AC"):
        numbers = sorted(
            int(name.split("-")[1]) for name in seen if name.startswith(prefix)
        )
        assert numbers == list(range(1, max(numbers) + 1)), (
            f"{prefix} numbering has a gap: {numbers}"
        )


def test_feature_004_continues_from_003():
    two = _defined_in(_read(ROOT / "specs" / "003-mobility-spectrum" / "spec.md"))
    three = _defined_in(_read(SPEC / "spec.md"))
    for prefix in ("FR", "NR", "AC"):
        old = {int(n.split("-")[1]) for n in two if n.startswith(prefix)}
        new = {int(n.split("-")[1]) for n in three if n.startswith(prefix)}
        if not new or not old:
            continue
        assert min(new) == max(old) + 1, (
            f"{prefix}: 004 starts at {min(new)}, 003 ends at {max(old)}"
        )


def test_the_specification_names_no_technology():
    found = sorted(set(FORBIDDEN_IN_SPEC.findall(_read(SPEC / "spec.md"))))
    assert not found, f"spec.md 004 names technology: {found}"


def _test_sources() -> str:
    here = pathlib.Path(__file__).name
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != here
    )


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


def test_the_two_traps_keep_the_numbers_that_found_them():
    """FR-082 and FR-083 both reverse an obvious implementation.

    Each cost an order of magnitude when it was done the obvious way, and a
    later editor who does not know that will do it the obvious way again. The
    measured numbers are the only thing that stops them.
    """
    record = SPEC / "research.md"
    if not record.exists():
        pytest.skip("the research record is not published with the program")
    research = _read(record)
    assert "1.587" in research and "0.043" in research, "the per-peak window"
    assert "0.427" in research, "the peak-list seed"

    spec = _read(SPEC / "spec.md")
    assert "per carrier type" in spec and "never per peak" in spec
    assert "distribution" in spec


def test_the_budget_is_required_to_bite_inside_the_fit():
    """NR-012. A budget checked between fits bounds nothing.

    The 2082-second fit of research 004 section 2 is one call to the solver,
    so an editor who moves the check outside the residual has removed it while
    appearing to keep it.
    """
    spec = _read(SPEC / "spec.md")
    assert "residual evaluation" in spec
    assert "while it is running" in spec


def test_conditioning_is_recorded_as_a_grade_and_not_a_gate():
    """FR-087. Gating on it rejected every combination from 30 to 60 K."""
    spec = _read(SPEC / "spec.md")
    assert "shall **not** be a gate" in spec
    record = SPEC / "research.md"
    if not record.exists():
        pytest.skip("the research record is not published with the program")
    research = _read(record)
    assert "not a gate" in research


def test_this_checker_has_no_mangled_escapes():
    text = pathlib.Path(__file__).read_bytes()
    for control in (b"\x08", b"\x0c", b"\x1b"):
        assert control not in text, f"control character {control!r} in the checker"
