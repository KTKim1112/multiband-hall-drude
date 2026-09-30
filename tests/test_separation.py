"""Splitting the measurement into hole and electron parts. FR-070, FR-071.

The identities are algebra, so they can be checked exactly rather than
approximately. What cannot be checked exactly is whether the Lorentzian
extension upstream is good enough to make them hold on real data; that is
`tests/test_spectrum.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit.core import lorentzian, separation
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, conductivity_tensor
from mbfit.core.units import density_to_si, mobility_to_si

FIELDS = np.round(np.linspace(-9.0, 9.0, 361), 6)

# An arbitrary known mixture chosen for this project.
DENSITY = [6.0e20, 1.8e21, 3.5e20, 2.0e21]
MOBILITY = [18000.0, 1800.0, 20000.0, 1070.0]
SIGN = [SIGN_HOLE, SIGN_HOLE, SIGN_ELECTRON, SIGN_ELECTRON]


def _exact():
    """X, Y, their transforms, and the true parts, all in closed form."""
    m = mobility_to_si(MOBILITY)
    zero = conductivity_tensor(
        np.array([0.0]), density_to_si(DENSITY), m, SIGN)[0][0]
    a = density_to_si(DENSITY) * 1.602176634e-19 * m / zero
    b = np.asarray(SIGN) * a * m

    X, Y = lorentzian.evaluate(FIELDS, a, b, m)
    Xt, Yt = lorentzian.transform(FIELDS, a, b, m)

    holes = [i for i, s in enumerate(SIGN) if s > 0]
    electrons = [i for i, s in enumerate(SIGN) if s < 0]
    true_Xp = sum(a[i] / (1 + (m[i] * FIELDS) ** 2) for i in holes)
    true_Xn = sum(a[i] / (1 + (m[i] * FIELDS) ** 2) for i in electrons)
    true_Yp = sum(a[i] * m[i] * FIELDS / (1 + (m[i] * FIELDS) ** 2) for i in holes)
    true_Yn = sum(a[i] * m[i] * FIELDS / (1 + (m[i] * FIELDS) ** 2) for i in electrons)
    return X, Y, Xt, Yt, true_Xp, true_Xn, true_Yp, true_Yn


def test_the_separation_recovers_the_true_parts():
    """Research 003 section 2.3, to machine precision."""
    X, Y, Xt, Yt, tXp, tXn, tYp, tYn = _exact()
    Xp, Xn, Yp, Yn = separation.separate(X, Y, Xt, Yt)

    for label, got, want in (
        ("X hole", Xp, tXp), ("X electron", Xn, tXn),
        ("Y hole", Yp, tYp), ("Y electron", Yn, tYn),
    ):
        error = np.max(np.abs(got - want)) / max(np.max(np.abs(want)), 1e-300)
        assert error < 1e-12, f"{label}: {error:.2e}"


def test_the_transform_is_the_all_hole_hall_and_the_measured_one_is_not():
    """The statement the whole feature turns on, as two assertions."""
    X, Y, Xt, Yt, tXp, tXn, tYp, tYn = _exact()
    assert np.allclose(Xt, tYp + tYn, rtol=0, atol=1e-15)   # every carrier a hole
    assert np.allclose(Y, tYp - tYn, rtol=0, atol=1e-15)    # the real signs
    # and the two really do differ, so the separation has something to work on
    assert np.max(np.abs(Xt - Y)) > 0.1 * np.max(np.abs(Y))


def test_the_parts_have_the_right_sign_for_a_physical_mixture():
    """The longitudinal parts are non-negative; the Hall parts follow the field.

    `Y^p` and `Y^n` are odd in field, so they are negative below zero field by
    construction. What they cannot do is disagree with the sign of the field,
    which is what passing `B_T` checks.
    """
    X, Y, Xt, Yt, *_ = _exact()
    Xp, Xn, Yp, Yn = separation.separate(X, Y, Xt, Yt)

    assert separation.negative_fraction(Xp) == 0.0
    assert separation.negative_fraction(Xn) == 0.0
    assert separation.negative_fraction(Yp, FIELDS) == 0.0
    assert separation.negative_fraction(Yn, FIELDS) == 0.0

    # and the Hall parts really are odd, so the check above is not vacuous
    assert np.min(Yp) < 0.0 < np.max(Yp)


def test_recombining_returns_the_measurement():
    X, Y, Xt, Yt, *_ = _exact()
    back_X, back_Y = separation.recombine(*separation.separate(X, Y, Xt, Yt))
    assert np.allclose(back_X, X, rtol=0, atol=1e-15)
    assert np.allclose(back_Y, Y, rtol=0, atol=1e-15)


# ------------------------------------------------------- the failure it reports

def test_a_negative_part_is_measured_and_not_repaired():
    """A separated conductivity cannot be negative; when it is, say so.

    Clipping would hide the one case a reader has to be told about, so
    `negative_fraction` returns how much went below zero and nothing touches
    the values.
    """
    part = np.array([1.0, 0.5, -0.5, -1.0])
    fraction = separation.negative_fraction(part)
    assert fraction == pytest.approx(np.linalg.norm([-0.5, -1.0]) / np.linalg.norm(part))
    assert 0.0 < fraction < 1.0


def test_an_all_positive_part_reports_nothing():
    assert separation.negative_fraction(np.array([3.0, 1.0, 0.0])) == 0.0


def test_an_odd_part_is_judged_against_the_field():
    B = np.array([-2.0, -1.0, 1.0, 2.0])
    good = np.array([-4.0, -1.0, 1.0, 4.0])       # odd, follows the field
    bad = np.array([+4.0, -1.0, 1.0, 4.0])        # one point of the wrong sign
    assert separation.negative_fraction(good, B) == 0.0
    assert separation.negative_fraction(bad, B) > 0.0


def test_an_empty_part_is_not_a_division_by_zero():
    assert separation.negative_fraction(np.zeros(5)) == 0.0


def test_mismatched_shapes_are_refused():
    with pytest.raises(ValueError):
        separation.separate(np.zeros(3), np.zeros(3), np.zeros(3), np.zeros(4))
