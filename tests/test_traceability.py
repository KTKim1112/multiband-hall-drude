"""Requirement coverage, checked mechanically rather than by reading.

`tasks.md` ends by promising this test. It extracts every requirement
identifier defined in `spec.md` and fails if any is absent from `tasks.md`,
so that a requirement added without a task breaks the build the moment it is
added rather than at the end of the project.

It also holds the two gates that were run by hand while the documents were
being written, so that they keep holding: no technology named in `spec.md`,
and the Korean translations referring to the same identifiers as their
English originals.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs" / "001-multiband-drude"
DOCS = ROOT / "docs"

REQUIREMENT = re.compile(r"\b((?:FR|NR|PM|AC)-\d{3})\b")
IDENTIFIER = re.compile(
    r"\b((?:FR|NR|PM|AC)-\d{3}"
    r"|[ED]_[A-Z][A-Z0-9_]*[A-Z0-9]"
    r"|T[1-7]\d{2}[bc]?"
    r"|K[1-9]"
    r"|C10|C[1-9]"
    r"|Q[1-9])\b"
)
FORBIDDEN_IN_SPEC = re.compile(
    r"\b(python|numpy|scipy|pandas|matplotlib|csv|json|dataframe|pytest|argparse)\b",
    re.IGNORECASE,
)

TRANSLATIONS = [
    (ROOT / ".specify" / "memory" / "constitution.md", DOCS / "constitution.ko.md"),
    (SPECS / "spec.md", DOCS / "spec.ko.md"),
    (SPECS / "research.md", DOCS / "research.ko.md"),
    (SPECS / "data-model.md", DOCS / "data-model.ko.md"),
    (SPECS / "plan.md", DOCS / "plan.ko.md"),
    (SPECS / "tasks.md", DOCS / "tasks.ko.md"),
    (SPECS / "quickstart.md", DOCS / "quickstart.ko.md"),
]
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


def test_every_requirement_is_reachable_from_a_task():
    defined = set(REQUIREMENT.findall(_read(SPECS / "spec.md")))
    scheduled = set(REQUIREMENT.findall(_read(SPECS / "tasks.md")))
    assert defined, "no requirements found in spec.md"
    missing = sorted(defined - scheduled)
    assert not missing, f"requirements with no task: {missing}"


def test_requirement_numbers_have_no_gaps():
    defined = set(REQUIREMENT.findall(_read(SPECS / "spec.md")))
    for prefix in ("FR", "NR", "PM", "AC"):
        numbers = sorted(
            {int(name.split("-")[1]) for name in defined if name.startswith(prefix)}
        )
        if not numbers:
            continue
        expected = list(range(1, max(numbers) + 1))
        assert numbers == expected, f"{prefix} numbering has gaps: {numbers}"


def test_the_specification_names_no_technology():
    """Rule 4.4 of the method: the document should still be true in ten years."""
    found = sorted(set(FORBIDDEN_IN_SPEC.findall(_read(SPECS / "spec.md"))))
    assert not found, f"spec.md names technology: {found}"


def test_every_diagnostic_code_is_reachable_from_a_task():
    declared = set(re.findall(r"\b(D_[A-Z][A-Z0-9_]*[A-Z0-9])\b", _read(SPECS / "data-model.md")))
    scheduled = _read(SPECS / "tasks.md")
    assert declared, "no diagnostic codes found in data-model.md"
    missing = sorted(code for code in declared if code not in scheduled)
    assert not missing, f"diagnostic codes with no task: {missing}"


def test_the_error_code_registry_matches_the_data_model():
    """Article IV, from the other side: the source and the document agree."""
    from mbfit.core.errors import ERROR_CODES

    document = _read(SPECS / "data-model.md")
    declared = set(re.findall(r"\b(E_[A-Z][A-Z0-9_]*[A-Z0-9])\b", document))
    in_source = set(ERROR_CODES)
    assert not (in_source - declared), f"code in source but not documented: {sorted(in_source - declared)}"
    assert not (declared - in_source), f"code documented but not in source: {sorted(declared - in_source)}"


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


# --------------------------------------------------------------- Gate 2

# Codes the source can raise but no test yet provokes. The list is allowed to
# shrink and never to grow: an entry here is a phase that has not happened.
NOT_YET_EXERCISED: set[str] = set()


def _test_sources() -> str:
    """Every test file except this one.

    This file names the deferred codes in NOT_YET_EXERCISED, so counting
    itself would let a code satisfy the check by being listed as unsatisfied.
    """
    here = pathlib.Path(__file__).name
    return chr(10).join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != here
    )


def test_every_error_code_is_provoked_by_a_test():
    """Gate 2, mechanically. A code nobody raises is a code nobody checked."""
    from mbfit.core.errors import ERROR_CODES

    sources = _test_sources()
    missing = sorted(
        code for code in ERROR_CODES
        if code not in NOT_YET_EXERCISED and code not in sources
    )
    assert not missing, f"error codes no test provokes: {missing}"


def test_the_deferred_list_is_accurate_and_never_stale():
    """A deferral that has quietly come true is a check nobody is making.

    The list may only hold codes that exist and that really are unexercised,
    so that it shrinks as the phases land and cannot be left behind.
    """
    from mbfit.core.errors import ERROR_CODES

    unknown = sorted(NOT_YET_EXERCISED - set(ERROR_CODES))
    assert not unknown, f"deferred codes that do not exist: {unknown}"

    sources = _test_sources()
    stale = sorted(code for code in NOT_YET_EXERCISED if code in sources)
    assert not stale, f"deferred but in fact exercised; remove from the list: {stale}"


def test_every_code_has_korean_wording():
    """Article IV from the presentation side: a code the user cannot read.

    The invariant is that every code in the source is declared in *a* data
    model and that every wording answers a declared code. There are two data
    models once feature 002 exists, so the check spans both; narrowing it to
    one would report feature 002's codes as wording for codes that do not
    exist.
    """
    from mbfit import messages
    from mbfit.core.errors import ERROR_CODES

    document = "\n".join(
        _read(path) for path in sorted((ROOT / "specs").glob("*/data-model.md"))
    )
    diagnostics = set(re.findall(r"\b(D_[A-Z][A-Z0-9_]*[A-Z0-9])\b", document))

    missing_errors = sorted(set(ERROR_CODES) - set(messages.ERROR_MESSAGES))
    missing_diagnostics = sorted(diagnostics - set(messages.DIAGNOSTIC_MESSAGES))
    assert not missing_errors, f"no wording for: {missing_errors}"
    assert not missing_diagnostics, f"no wording for: {missing_diagnostics}"

    extra = sorted(set(messages.MESSAGES) - set(ERROR_CODES) - diagnostics)
    assert not extra, f"wording for codes that do not exist: {extra}"


def test_describe_carries_the_code_and_the_detail():
    from mbfit import messages

    rendered = messages.describe("E_DATA_MISSING_COLUMN", {"missing": ["rxy"]})
    assert "E_DATA_MISSING_COLUMN" in rendered
    assert "rxy" in rendered
