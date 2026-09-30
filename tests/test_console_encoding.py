"""The Korean console, enforced.

`cli.py` and `messages.py` are the only two places human-facing wording
lives, and the console that wording reaches is a Korean Windows one: code
page 949. cp949 carries every Hangul syllable, so the Korean itself is never
the problem. What it does not carry is U+2014 EM DASH.

One of those on line 61 of `cli.py` was enough to end a run with
`UnicodeEncodeError`, and it ended immediately before the warning block --
the thing this program exists to produce. The fit had already converged and
the output files had already been written, so the crash cost the user
precisely the part that mattered and nothing else. Nothing in the suite saw
it, because every test either captures stdout through UTF-8 or never renders
that line at all.

Two guards here, because they fail in different ways and the cheap one is
not sufficient. The first keeps such a character out of the source. The
second drives the command line against a real cp949 stream, so a character
arriving from somewhere the first guard does not read -- an interpolated
value, a future module -- still cannot take the diagnostics down with it.

U+2015 HORIZONTAL BAR is the substitute the source now uses. It is in cp949,
it is in UTF-8, and it renders as the same dash.
"""

from __future__ import annotations

import io
import json
import pathlib
import sys

from mbfit import messages
from mbfit.cli import main

from test_cli import BASE_CONFIG, EXAMPLE

CONSOLE_ENCODING = "cp949"
PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "mbfit"
PRESENTATION_LAYER = ("cli.py", "messages.py")

EM_DASH = chr(0x2014)  # not in cp949 -- this is the character that broke it
HORIZONTAL_BAR = chr(0x2015)  # in cp949, and the one the source uses now
# U+ACBD U+ACE0, the Korean for "warning", which heads the block that was lost.
WARNING_HEADING = chr(0xACBD) + chr(0xACE0)


def _unencodable(text: str):
    offences = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for character in line:
            try:
                character.encode(CONSOLE_ENCODING)
            except UnicodeEncodeError:
                offences.append(f"line {line_number}: U+{ord(character):04X}")
    return offences


# ========================================= guard one: keep it out of source

def test_the_presentation_layer_encodes_on_a_korean_console():
    offences = []
    for name in PRESENTATION_LAYER:
        for offence in _unencodable((PACKAGE / name).read_text(encoding="utf-8")):
            offences.append(f"{name} {offence}")
    assert not offences, (
        "text that a cp949 console cannot render, so printing it ends the run: "
        + "; ".join(offences[:20])
    )


def test_the_check_would_catch_the_character_that_broke_it():
    """A guard that passes on the original defect would be worth nothing."""
    assert _unencodable(EM_DASH), "U+2014 must be reported, it is what crashed"
    assert not _unencodable(HORIZONTAL_BAR), "U+2015 is the substitute, it must pass"


# ================================ guard two: survive it if it gets in anyway

def _run_with_console(encoding: str, tmp_path):
    """Run the command line writing to a stream with the given encoding."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps(BASE_CONFIG), encoding="utf-8")

    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding=encoding, newline="")
    original = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = console
    try:
        code = main(["--data", str(EXAMPLE), "--config", str(config),
                     "--out", str(tmp_path / "out")])
        console.flush()
    finally:
        sys.stdout, sys.stderr = original
    return code, raw.getvalue().decode(encoding)


def test_the_diagnostics_reach_a_cp949_console(tmp_path):
    """The end-to-end reproduction. This is the test the defect would fail."""
    code, printed = _run_with_console(CONSOLE_ENCODING, tmp_path)
    assert code == 0
    assert WARNING_HEADING in printed, (
        "the warning block is the reason this program exists and it did not print"
    )
    assert "D_R2_BELOW" in printed


def test_an_unencodable_character_degrades_instead_of_ending_the_run(tmp_path, monkeypatch):
    """`_resilient_console` earns its place only if the run survives one.

    The heading is put back the way it was, U+2014 and all. On a cp949
    console the character cannot be rendered, but the diagnostics that
    follow it must still arrive.
    """
    from mbfit import cli

    monkeypatch.setattr(
        cli, "describe",
        lambda code, detail: EM_DASH + " " + messages.describe(code, detail),
    )
    code, printed = _run_with_console(CONSOLE_ENCODING, tmp_path)
    assert code == 0
    assert "D_R2_BELOW" in printed
    assert WARNING_HEADING in printed
