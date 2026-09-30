"""Feature 003 documents, and the numbering across all three. Gate 13.

The append-only rule now spans three specifications, so the check that
requirement numbers have no gaps and no reuse has to look at all of them at
once. A fourth feature will extend the tuple below and nothing else.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = sorted((ROOT / "specs").glob("*/spec.md"))
SPEC_003 = ROOT / "specs" / "003-mobility-spectrum"
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
    r"|T(?:11|12|13)\d{2}"
    r"|K[1-9]"
    r"|C10|C[1-9]"
    r"|Q10|Q[1-9])\b"
)
FORBIDDEN_IN_SPEC = re.compile(
    r"\b(python|numpy|scipy|pandas|matplotlib|csv|json|dataframe|pytest|argparse)\b",
    re.IGNORECASE,
)

TRANSLATIONS = (
    (SPEC_003 / "spec.md", DOCS / "003-spec.ko.md"),
    (SPEC_003 / "research.md", DOCS / "003-research.ko.md"),
    (SPEC_003 / "data-model.md", DOCS / "003-data-model.ko.md"),
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
    defined = _defined_in(_read(SPEC_003 / "spec.md"))
    scheduled = set(REQUIREMENT.findall(_read(SPEC_003 / "tasks.md")))
    assert defined, "no requirements found in spec.md 003"
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


def test_feature_003_continues_from_002():
    two = _defined_in(_read(ROOT / "specs" / "002-uncertainty-and-discriminants" / "spec.md"))
    three = _defined_in(_read(SPEC_003 / "spec.md"))
    for prefix in ("FR", "NR", "AC"):
        old = {int(n.split("-")[1]) for n in two if n.startswith(prefix)}
        new = {int(n.split("-")[1]) for n in three if n.startswith(prefix)}
        if not new or not old:
            continue
        assert min(new) == max(old) + 1, (
            f"{prefix}: 003 starts at {min(new)}, 002 ends at {max(old)}"
        )


def test_the_specification_names_no_technology():
    found = sorted(set(FORBIDDEN_IN_SPEC.findall(_read(SPEC_003 / "spec.md"))))
    assert not found, f"spec.md 003 names technology: {found}"


def test_every_new_diagnostic_code_is_reachable_from_a_task():
    declared = set(DIAGNOSTIC.findall(_read(SPEC_003 / "data-model.md")))
    scheduled = _read(SPEC_003 / "tasks.md")
    assert declared, "no diagnostic codes found in data-model.md 003"
    missing = sorted(code for code in declared if code not in scheduled)
    assert not missing, f"diagnostic codes with no task: {missing}"


def _test_sources() -> str:
    here = pathlib.Path(__file__).name
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != here
    )


def test_every_new_diagnostic_code_is_provoked_by_a_test():
    declared = set(DIAGNOSTIC.findall(_read(SPEC_003 / "data-model.md")))
    sources = _test_sources()
    missing = sorted(code for code in declared if code not in sources)
    assert not missing, f"diagnostic codes no test provokes: {missing}"


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


def test_the_restriction_on_composing_the_discriminants_is_recorded():
    """FR-078 exists because two sound tools give a wrong answer together.

    It is the kind of finding that gets edited out as a needless caveat, so
    the measurement that produced it is pinned here as well as stated there.
    """
    record = SPEC_003 / "research.md"
    if not record.exists():
        pytest.skip("the research record is not published with the program")
    research = _read(record)
    assert "Composing them is" in research
    assert "FR-078" in _read(SPEC_003 / "spec.md")


def test_the_closed_form_transform_is_required_not_merely_used():
    """NR-009. The published method integrates numerically; this one must not.

    A later editor reaching for a quadrature would be undoing the one place
    this implementation is better than the method it follows.
    """
    spec = _read(SPEC_003 / "spec.md")
    assert "No numerical" in spec and "principal-value integral" in spec


def test_this_checker_has_no_mangled_escapes():
    text = pathlib.Path(__file__).read_bytes()
    for control in (b"\x08", b"\x0c", b"\x1b"):
        assert control not in text, f"control character {control!r} in the checker"
