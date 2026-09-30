"""Feature 002 documents, checked the way feature 001's are.

The same invariants, plus one that only exists once there are two features:
requirement numbers are append-only **across the project**, so the union of
the two specifications must run from 1 with no gaps and nothing defined twice.
A renumbering would silently break every citation in every commit message
written so far.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_001 = ROOT / "specs" / "001-multiband-drude"
SPEC_002 = ROOT / "specs" / "002-uncertainty-and-discriminants"
DOCS = ROOT / "docs"

REQUIREMENT = re.compile(r"\b((?:FR|NR|PM|AC)-\d{3})\b")
DIAGNOSTIC = re.compile(r"\b(D_[A-Z][A-Z0-9_]*[A-Z0-9])\b")

# A requirement is *defined* where it is bolded at the start of a list item or
# a paragraph, as in `- **FR-058** The program shall ...`, or where it opens a
# table row, as the acceptance criteria do. Everywhere else it is a citation:
# feature 002 refers to FR-046 and FR-057 of feature 001 without redefining
# them, and a check that cannot tell the two apart reports that as a duplicate.
DEFINITION = re.compile(
    r"^(?:- )?\*\*((?:FR|NR|PM|AC)-\d{3})\.?\*\*"
    r"|^\|\s*((?:FR|NR|PM|AC)-\d{3})\s*\|",
    re.MULTILINE,
)

IDENTIFIER = re.compile(
    r"\b((?:FR|NR|PM|AC)-\d{3}"
    r"|[ED]_[A-Z][A-Z0-9_]*[A-Z0-9]"
    r"|T(?:8|9|10)\d{2}"
    r"|K[1-9]"
    r"|C10|C[1-9]"
    r"|Q[1-9])\b"
)
FORBIDDEN_IN_SPEC = re.compile(
    r"\b(python|numpy|scipy|pandas|matplotlib|csv|json|dataframe|pytest|argparse)\b",
    re.IGNORECASE,
)

TRANSLATIONS = (
    (SPEC_002 / "spec.md", DOCS / "002-spec.ko.md"),
    (SPEC_002 / "research.md", DOCS / "002-research.ko.md"),
    (SPEC_002 / "data-model.md", DOCS / "002-data-model.ko.md"),
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
    defined = _defined_in(_read(SPEC_002 / "spec.md"))
    scheduled = set(REQUIREMENT.findall(_read(SPEC_002 / "tasks.md")))
    assert defined, "no requirements found in spec.md 002"
    missing = sorted(defined - scheduled)
    assert not missing, f"requirements with no task: {missing}"


def test_the_two_features_together_have_no_gaps_and_no_reuse():
    """Append-only numbering, enforced across features rather than within one."""
    one = _defined_in(_read(SPEC_001 / "spec.md"))
    two = _defined_in(_read(SPEC_002 / "spec.md"))

    reused = sorted(one & two)
    assert not reused, f"requirement defined in both features: {reused}"

    for prefix in ("FR", "NR", "AC"):
        numbers = sorted(
            {int(name.split("-")[1]) for name in (one | two) if name.startswith(prefix)}
        )
        assert numbers == list(range(1, max(numbers) + 1)), (
            f"{prefix} numbering across features has a gap: {numbers}"
        )


def test_feature_002_continues_rather_than_restarts():
    """The first new number of each kind follows the last old one."""
    one = _defined_in(_read(SPEC_001 / "spec.md"))
    two = _defined_in(_read(SPEC_002 / "spec.md"))
    for prefix in ("FR", "NR", "AC"):
        old = {int(n.split("-")[1]) for n in one if n.startswith(prefix)}
        new = {int(n.split("-")[1]) for n in two if n.startswith(prefix)}
        if not new:
            continue
        assert min(new) == max(old) + 1, (
            f"{prefix}: feature 002 starts at {min(new)}, feature 001 ends at {max(old)}"
        )


def test_the_specification_names_no_technology():
    found = sorted(set(FORBIDDEN_IN_SPEC.findall(_read(SPEC_002 / "spec.md"))))
    assert not found, f"spec.md 002 names technology: {found}"


def test_every_new_diagnostic_code_is_reachable_from_a_task():
    """Gate 8 and Gate 9: a code nothing can raise is a code nobody will see."""
    declared = set(DIAGNOSTIC.findall(_read(SPEC_002 / "data-model.md")))
    scheduled = _read(SPEC_002 / "tasks.md")
    assert declared, "no diagnostic codes found in data-model.md 002"
    missing = sorted(code for code in declared if code not in scheduled)
    assert not missing, f"diagnostic codes with no task: {missing}"


# Codes declared by feature 002 that no test provokes yet, with the phase that
# will. The list may only hold codes that exist and really are unexercised, so
# it shrinks as the phases land and cannot be left behind.
#
# It held D_INTERVAL_LOWER_BOUND until Phase 9, and the staleness check below
# is what removed it: the entry failed the moment the code was first raised by
# a test, rather than sitting here unnoticed once it had come true.
NOT_YET_EXERCISED: dict[str, str] = {}


def _test_sources() -> str:
    here = pathlib.Path(__file__).name
    return chr(10).join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != here
    )


def test_every_new_diagnostic_code_is_provoked_by_a_test():
    """Gate 8, mechanically. A code no test raises is a code nobody checked."""
    declared = set(DIAGNOSTIC.findall(_read(SPEC_002 / "data-model.md")))
    sources = _test_sources()
    missing = sorted(
        code for code in declared
        if code not in NOT_YET_EXERCISED and code not in sources
    )
    assert not missing, f"diagnostic codes no test provokes: {missing}"


def test_the_deferred_list_is_accurate_and_never_stale():
    declared = set(DIAGNOSTIC.findall(_read(SPEC_002 / "data-model.md")))
    unknown = sorted(set(NOT_YET_EXERCISED) - declared)
    assert not unknown, f"deferred codes that are not declared: {unknown}"

    sources = _test_sources()
    stale = sorted(code for code in NOT_YET_EXERCISED if code in sources)
    assert not stale, f"deferred but in fact exercised; remove from the list: {stale}"


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


def test_the_rejected_sign_convention_stays_rejected():
    """Research 002 section 5.1, guarded rather than merely written down.

    The external design note proposes the inversion that PM-001 replaced. The
    number that separates them is recorded in research 001 section 2.1, and a
    future editor reaching for the note's formulas should trip this.
    """
    record = SPEC_002 / "research.md"
    if not record.exists():
        pytest.skip("the research record is not published with the program")
    research = _read(record)
    assert "187.24527" in research
    assert "PM-001 stands" in research


def test_this_checker_has_no_mangled_escapes():
    """A guard the project has earned twice over.

    Writing this file through a shell heredoc has twice turned a regular
    expression escape into a literal backspace, which matches nothing and
    quietly empties the set the assertions above are built on. A control
    character in a source file here is never intentional.
    """
    text = pathlib.Path(__file__).read_bytes()
    for control in (b"\x08", b"\x0c", b"\x1b"):
        assert control not in text, f"control character {control!r} in the checker"
