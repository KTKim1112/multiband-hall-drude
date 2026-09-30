"""T1304 -- the sentences that go out with every spectrum. FR-076, FR-077.

A spectrum is a picture with peaks on it, and a peak looks exactly like a
band. Nothing in the CSV files says otherwise, so the correction has to travel
with the result rather than wait in a document. Article VI puts the evidence
against trusting an answer beside the answer; these three sentences are that,
for the one claim a reader is most likely to make unaided.

They are pinned here by what they must *say*, not by their exact wording, so
the Korean can be improved without breaking the test -- but not silently
dropped, and not weakened into a hedge that no longer names the three things
research 003 measured.
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from mbfit import cli

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_notice_states_a_peak_is_a_channel_and_not_a_band():
    """FR-076 in its most quotable form."""
    notice = cli.SPECTRUM_NOTICE
    assert "전도 채널" in notice
    assert "Fermi surface" in notice
    assert "상한" in notice, "a peak count bounds the band count, it does not estimate it"


def test_the_notice_carries_the_measurement_behind_the_claim():
    """Article VI: a claim a reader is asked to accept names its evidence.

    Four cyclotron harmonics of one orbit came back as three peaks, in
    research 003 section 7. Without the number the sentence is an opinion, and
    a reader with a four-peak spectrum has no way to judge how much of it to
    discount.
    """
    notice = cli.SPECTRUM_NOTICE
    assert "research 003" in notice
    assert "4" in notice and "3" in notice


def test_the_notice_says_the_peaks_sit_where_the_extension_put_them():
    """FR-077. The limit that is invisible from the output files.

    Every peak lies on a mobility the Lorentzian extension chose, so a reader
    who does not know that will read a gap in the spectrum as a fact about the
    sample when it may be a fact about the extension order they declared.
    """
    notice = cli.SPECTRUM_NOTICE
    assert "확장" in notice
    assert "이동도" in notice


def test_the_notice_says_the_count_is_still_the_readers_to_declare():
    """FR-076. The proposal never overrides the declared carriers."""
    assert "carrier 개수" in cli.SPECTRUM_NOTICE
    assert "제안" in cli.SPECTRUM_NOTICE


def test_the_notice_reaches_the_console_when_a_spectrum_is_produced(tmp_path):
    """And only then: a run without a spectrum must not carry the caveat.

    A warning that appears when it does not apply is a warning readers learn
    to skip, which costs the times it does apply.
    """
    from test_cli import BASE_CONFIG, EXAMPLE

    def run(spectrum_on):
        document = json.loads(json.dumps(BASE_CONFIG))
        document["spectrum"] = {
            "enabled": spectrum_on, "lorentzian_terms": 4,
            "lorentzian_multi_start": 4,
        }
        path = tmp_path / f"config_{spectrum_on}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        out = tmp_path / f"out_{spectrum_on}"
        stream = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(stream):
            cli.main([
                "--data", str(EXAMPLE), "--config", str(path), "--out", str(out),
            ])
        return stream.getvalue()

    # not "전도 채널": the effective-mobility notice of FR-064 uses that
    # phrase too and goes out on every run, so it cannot tell the two apart.
    assert "사이클로트론" in run(True)
    assert "사이클로트론" not in run(False)
