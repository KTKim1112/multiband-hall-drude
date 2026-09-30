"""Constitution Articles IV and VIII, enforced.

The library signals failure by a code, never by a sentence. Human-facing
wording -- all of the Korean -- lives only in the presentation layer, which is
`mbfit/messages.py` and `mbfit/cli.py`. Everywhere else in the package the
source is ASCII.

Two things follow that are worth the test on their own. A test asserts on
`E_DATA_MISSING_COLUMN`, not on a sentence that changes whenever the wording
improves. And the computational source stays free of text that a terminal,
an editor or a diff tool may render differently.
"""

from __future__ import annotations

import pathlib
import re

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "mbfit"
PRESENTATION_LAYER = {"messages.py", "cli.py"}

SCREEN = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src"
# Hangul syllables and compatibility jamo, built with chr rather than
# written out, so that this file satisfies the rule it enforces.
HANGUL = re.compile(
    "[" + chr(0xAC00) + "-" + chr(0xD7AF) + chr(0x3130) + "-" + chr(0x318F) + "]"
)


def test_the_screens_sentences_live_only_where_a_language_is_written():
    """Article VIII. The screen speaks two languages now, and neither may be
    written into a component: a sentence in a component is a sentence the other
    language does not have, and no build can catch that."""
    if not SCREEN.is_dir():
        pytest.skip("frontend not present")
    offences = [
        str(path.relative_to(SCREEN))
        for path in sorted(SCREEN.rglob("*.ts*"))
        if path.parent.name != "text" and HANGUL.search(path.read_text(encoding="utf-8"))
    ]
    assert not offences, f"Korean outside frontend/src/text/: {offences}"


def _package_modules():
    return sorted(PACKAGE.rglob("*.py"))


def test_package_directory_is_not_empty():
    assert _package_modules(), "no modules found under mbfit/"


def test_no_non_ascii_outside_the_presentation_layer():
    offences = []
    for path in _package_modules():
        if path.name in PRESENTATION_LAYER:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for column, character in enumerate(line, start=1):
                if ord(character) > 127:
                    offences.append(
                        f"{path.relative_to(PACKAGE)}:{line_number}:{column} "
                        f"U+{ord(character):04X}"
                    )
                    break
    assert not offences, (
        "Article IV and VIII: non-ASCII outside messages.py and cli.py. "
        + "; ".join(offences[:20])
    )


def test_this_test_file_is_itself_ascii():
    """A checker written in the thing it forbids would be hard to trust."""
    text = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert all(ord(character) <= 127 for character in text)


def test_the_check_would_catch_a_violation():
    """The enforcement itself is tested, on text that is never imported.

    The offending characters are built with `chr` rather than written out, so
    that this file satisfies the rule it enforces.
    """
    ascii_only = 'raise MbfitError("E_DATA_MISSING_COLUMN")'
    # U+C5F4 U+C744, the first two syllables of the Korean for "the column".
    with_korean = 'raise MbfitError("' + chr(0xC5F4) + chr(0xC744) + '")'
    assert all(ord(character) <= 127 for character in ascii_only)
    assert any(ord(character) > 127 for character in with_korean)
