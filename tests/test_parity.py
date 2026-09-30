"""T803 — parity violation at intake. Gate 8.

FR-065. Symmetrising removes the contact admixture; it does not say how much
it removed. That number is the only evidence a sweep carries about its own
contact geometry, and it is destroyed by the very step that fixes it, so it
has to be taken first.

The reference sweeps arrive already symmetrised, so on them the metric reads
zero. A test that only checked those would pass on an implementation that
returns zero unconditionally, which is why the admixture case below is the
one that matters.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio
from mbfit.core import parity

ROOT = pathlib.Path(__file__).resolve().parent.parent
THRESHOLD = 0.02          # AC-015


@pytest.fixture(scope="module")
def sweep():
    config = cfg.resolve(json.loads(
        (ROOT / "configs" / "synthetic_5K.json").read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    return dataset.groups[0]


# ------------------------------------------------------------ the clean case

def test_the_reference_sweep_violates_neither_parity(sweep):
    assert parity.violation(sweep.B_T, sweep.rhoxx_uohmcm, parity.PARITY_EVEN) == 0.0
    assert parity.violation(sweep.B_T, sweep.rhoxy_uohmcm, parity.PARITY_ODD) == 0.0


def test_both_polarities_are_present(sweep):
    assert parity.both_polarities(sweep.B_T)


# --------------------------------------------------- the case that matters

def test_GATE8_a_longitudinal_admixture_is_measured(sweep):
    """The defect FR-065 exists to catch: contacts not exactly opposite.

    A fraction `f` of the longitudinal voltage appearing in the Hall channel
    does not change sign with the field, so it is an even contamination of an
    odd channel. The measured violation should track `f` times the ratio of
    the two channel sizes.
    """
    B, xx, xy = sweep.B_T, sweep.rhoxx_uohmcm, sweep.rhoxy_uohmcm
    # The metric pairs each positive field with its mirror, so the expectation
    # is over the positive half, not over the whole sweep: the two differ by
    # the B = 0 record, which the even channel has and the odd one does not.
    half = B > 0
    for fraction in (0.001, 0.01, 0.05):
        contaminated = xy + fraction * xx
        measured = parity.violation(B, contaminated, parity.PARITY_ODD)
        expected = fraction * np.linalg.norm(xx[half]) / np.linalg.norm(xy[half])
        assert measured == pytest.approx(expected, rel=1e-9)

    # and it crosses AC-015 where it should
    small = parity.violation(B, xy + 0.001 * xx, parity.PARITY_ODD)
    large = parity.violation(B, xy + 0.05 * xx, parity.PARITY_ODD)
    assert small < THRESHOLD < large


def test_a_hall_admixture_into_the_longitudinal_channel_is_measured(sweep):
    """The mirror defect, odd contamination of an even channel."""
    B, xx, xy = sweep.B_T, sweep.rhoxx_uohmcm, sweep.rhoxy_uohmcm
    half = B > 0
    measured = parity.violation(B, xx + 0.10 * xy, parity.PARITY_EVEN)
    expected = 0.10 * np.linalg.norm(xy[half]) / np.linalg.norm(xx[half])
    assert measured == pytest.approx(expected, rel=1e-9)


def test_symmetrising_destroys_the_evidence(sweep):
    """Why FR-065 says "before any symmetrisation is applied"."""
    B, xx, xy = sweep.B_T, sweep.rhoxx_uohmcm, sweep.rhoxy_uohmcm
    contaminated = xy + 0.05 * xx
    before = parity.violation(B, contaminated, parity.PARITY_ODD)

    symmetrised = 0.5 * (contaminated - contaminated[::-1])
    after = parity.violation(B, symmetrised, parity.PARITY_ODD)

    assert before > THRESHOLD
    assert after == pytest.approx(0.0, abs=1e-12)


# ------------------------------------------------------------------- FR-066

def test_one_polarity_only_is_unmeasured_rather_than_zero(sweep):
    """A sweep with no negative fields cannot be checked, and must say so."""
    half = sweep.B_T > 0
    B, xy = sweep.B_T[half], sweep.rhoxy_uohmcm[half]

    assert not parity.both_polarities(B)
    assert parity.violation(B, xy, parity.PARITY_ODD) is None


def test_a_partial_overlap_uses_only_the_paired_fields(sweep):
    """Records without a mirror are excluded rather than assumed symmetric."""
    keep = (sweep.B_T >= -4.0)
    B, xy, xx = sweep.B_T[keep], sweep.rhoxy_uohmcm[keep], sweep.rhoxx_uohmcm[keep]
    measured = parity.violation(B, xy + 0.05 * xx, parity.PARITY_ODD)
    assert measured is not None and measured > 0.0

    paired = (B > 0) & (B <= 4.0)
    expected = 0.05 * np.linalg.norm(xx[paired]) / np.linalg.norm(xy[paired])
    assert measured == pytest.approx(expected, rel=1e-9)


def test_a_rejected_parity_argument_is_rejected():
    with pytest.raises(ValueError):
        parity.violation(np.array([-1.0, 1.0]), np.array([1.0, 1.0]), 0)
