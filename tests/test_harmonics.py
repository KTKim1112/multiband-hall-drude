"""T802 — the Fermi-surface discriminant. Gate 8.

Research 002 section 4: a single non-circular orbit, expanded in cyclotron
harmonics, produces the multiband Drude form with mobilities `mu, mu/2,
mu/3, ...`. The test has to do two things, and the second is the one that
matters. It has to recognise such a ladder when it is there, and it has to
report the real carriers of this sample as **not** one -- because if it
cannot tell them apart it is decoration.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, fitting
from mbfit.core import harmonics

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOLERANCE = 0.05          # AC-014

SWEEPS = (
    ("5K", "synthetic_5K"),
    ("20K", "synthetic_20K"),
    ("40K", "synthetic_40K"),
)


# ------------------------------------------------------- it recognises a ladder

def test_a_textbook_ladder_is_recognised():
    """Four harmonics of one orbit: mu, mu/2, mu/3, mu/4, weights falling."""
    mu = np.array([20000.0, 10000.0, 20000.0 / 3.0, 5000.0])
    n = np.array([4e20, 2e20, 1e20, 5e19])
    sign = np.array([1.0, 1.0, 1.0, 1.0])

    found = harmonics.verdict(n, mu, sign, TOLERANCE)
    assert found["is_ladder"]
    assert found["failed"] == ()
    assert list(found["harmonics"]) == [1, 2, 3, 4]


def test_a_ladder_survives_a_perturbation_inside_the_tolerance():
    mu = np.array([20000.0, 10000.0 * 1.03, 20000.0 / 3.0, 5000.0 * 0.98])
    n = np.array([4e20, 2e20, 1e20, 5e19])
    sign = np.ones(4)
    assert harmonics.verdict(n, mu, sign, TOLERANCE)["is_ladder"]


def test_a_ladder_fails_once_the_ratios_drift_outside_it():
    mu = np.array([20000.0, 10000.0 * 1.30, 20000.0 / 3.0, 5000.0])
    n = np.array([4e20, 2e20, 1e20, 5e19])
    sign = np.ones(4)
    found = harmonics.verdict(n, mu, sign, TOLERANCE)
    assert not found["is_ladder"]
    assert "consecutive_integers" in found["failed"]


def test_the_sign_condition_alone_rejects_an_otherwise_perfect_ladder():
    """The sharpest of the three. Research 002 section 4.

    Harmonics of one orbit cannot change the sign of the charge carrying it,
    so a mixed-sign set is not a ladder however well its ratios behave.
    """
    mu = np.array([20000.0, 10000.0, 20000.0 / 3.0, 5000.0])
    n = np.array([4e20, 2e20, 1e20, 5e19])
    mixed = np.array([1.0, 1.0, -1.0, 1.0])

    found = harmonics.verdict(n, mu, mixed, TOLERANCE)
    assert not found["is_ladder"]
    assert found["failed"] == ("single_sign",)
    # and the ratios really were a ladder, so nothing else carried the verdict
    assert list(found["harmonics"]) == [1, 2, 3, 4]


def test_rising_weights_are_rejected():
    mu = np.array([20000.0, 10000.0, 20000.0 / 3.0])
    n = np.array([1e20, 2e20, 4e20])
    found = harmonics.verdict(n, mu, np.ones(3), TOLERANCE)
    assert not found["is_ladder"]
    assert found["failed"] == ("falling_weights",)


def test_a_far_ratio_is_no_match_rather_than_a_high_harmonic():
    """Every number is near some integer; a ladder is not every number."""
    assert harmonics.nearest_harmonic(np.array([18.52]), TOLERANCE)[0] == 0
    assert harmonics.nearest_harmonic(np.array([3.0]), TOLERANCE)[0] == 3


# ------------------------------------------- and it clears the real carriers

@pytest.fixture(scope="module")
def fitted():
    out = {}
    for tag, config_name in SWEEPS:
        config = cfg.resolve(json.loads(
            (ROOT / "configs" / f"{config_name}.json").read_text(encoding="utf-8")))
        dataset = dataio.load_dataset(ROOT / "tests" / "data" / f"synthetic_{tag}.csv", config)
        fit = fitting.fit_temperature(dataset.groups[0], config)
        out[tag] = fit
    return out


@pytest.mark.parametrize("tag", [tag for tag, _ in SWEEPS])
def test_GATE8_the_real_carriers_are_not_a_harmonic_ladder(fitted, tag):
    """Research 002 section 4.1, at all three temperatures.

    This removes one of the three explanations research 001 Q4 leaves open
    for the 3 % misfit. It fails on the sign condition, which is the
    strongest way to fail it: no arrangement of the tolerance rescues it.
    """
    fit = fitted[tag]
    params = fit.params_canonical
    sign = fitting.signs(fit.specs)

    found = harmonics.verdict(params[0::2], params[1::2], sign, TOLERANCE)
    assert not found["is_ladder"]
    assert "single_sign" in found["failed"]


def test_the_recorded_ratios_come_back(fitted):
    """The same quantity research 002 section 4.1 tabulates, on this fixture.

    Section 4.1 tabulates `1.08, 11.0, 18.5` at 5 K and so on, measured on the
    supplied sweeps. Those sweeps are a sample's and are not published with
    this program, so the numbers below are the ladder ratios of the synthetic
    fixture, re-recorded when it replaced them. The document is not wrong and
    is not restated here: it records what the measurement gave.
    """
    expected = {
        "5K": [1.00, 1.09, 9.41, 12.04],
        "20K": [1.00, 1.10, 9.24, 10.91],
        "40K": [1.00, 1.18, 6.34, 16.59],
    }
    for tag, wanted in expected.items():
        params = fitted[tag].params_canonical
        _, ratios = harmonics.ladder_ratios(params[1::2])
        assert ratios == pytest.approx(wanted, rel=0.02)


def test_nothing_sits_at_the_second_or_third_rung(fitted):
    """A ladder needs its intermediate rungs, and they carry the larger weight.

    The 11.0 of the 5 K set is close to an integer, but a ladder that jumps
    from 1 to 11 is not a ladder. This is the check that stops a near-integer
    coincidence being read as evidence.
    """
    for tag, _ in SWEEPS:
        params = fitted[tag].params_canonical
        _, ratios = harmonics.ladder_ratios(params[1::2])
        assert not np.any(np.abs(ratios - 2.0) <= 2.0 * TOLERANCE)
        assert not np.any(np.abs(ratios - 3.0) <= 3.0 * TOLERANCE)
