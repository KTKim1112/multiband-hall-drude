"""The Lorentzian extension and its exact Kramers-Kronig transform.

The closed forms are the reason this feature needs no numerical
principal-value integral, so they are checked against a direct quadrature
rather than taken on trust. Everything downstream rests on them.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from mbfit.core import lorentzian
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, conductivity_tensor
from mbfit.core.units import density_to_si, mobility_to_si

FIELDS = np.round(np.linspace(-9.0, 9.0, 361), 6)


def _hilbert_by_quadrature(f, B):
    """H[f](B) = (1/pi) P integral f(B')/(B - B') dB', done numerically.

    Substituting `B' = B + s` turns the principal value into
    `-(1/pi) integral_0^inf [f(B+s) - f(B-s)]/s ds`, where the singularity has
    cancelled between the two branches. The range is split because a single
    call over fifteen decades is reported divergent by the quadrature.
    """
    def integrand(s):
        return (f(B + s) - f(B - s)) / s

    edges = [1e-10, 1e-4, 1e-2, 1.0, 10.0, 1e3, 1e6, 1e9]
    total = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        value, _ = quad(integrand, low, high, limit=500)
        total += value
    return -total / np.pi


@pytest.mark.parametrize("mu", [0.4, 3.0, 12.0])
@pytest.mark.parametrize("B", [0.3, 1.0, 2.5, -1.7])
def test_the_even_kernel_transforms_to_the_odd_one(mu, B):
    """H[1/(1+mu^2 B^2)] = mu B/(1+mu^2 B^2), to the quadrature's accuracy."""
    measured = _hilbert_by_quadrature(lambda b: 1.0 / (1.0 + (mu * b) ** 2), B)
    closed = mu * B / (1.0 + (mu * B) ** 2)
    assert measured == pytest.approx(closed, rel=1e-6)


@pytest.mark.parametrize("mu", [0.4, 3.0, 12.0])
@pytest.mark.parametrize("B", [0.3, 1.0, 2.5, -1.7])
def test_the_odd_kernel_transforms_to_the_even_one(mu, B):
    """H[B/(1+mu^2 B^2)] = -(1/mu)/(1+mu^2 B^2)."""
    measured = _hilbert_by_quadrature(lambda b: b / (1.0 + (mu * b) ** 2), B)
    closed = -(1.0 / mu) / (1.0 + (mu * B) ** 2)
    assert measured == pytest.approx(closed, rel=1e-6)


def test_the_transform_of_a_sum_is_the_sum_of_the_transforms():
    a = np.array([0.5, 0.3, 0.2])
    b = np.array([0.4, -0.2, 0.05])
    mu = np.array([2.0, 0.5, 0.08])

    Xt, Yt = lorentzian.transform(FIELDS, a, b, mu)
    for index, B in enumerate(FIELDS[::40]):
        want_X = _hilbert_by_quadrature(
            lambda t: float(lorentzian.evaluate(np.array([t]), a, b, mu)[0][0]), B)
        assert Xt[index * 40] == pytest.approx(want_X, rel=1e-5, abs=1e-9)


# --------------------------------------------------- the model matches drude.py

def test_the_lorentzian_form_is_the_drude_model_normalised():
    """Research 003 section 2: nothing new is assumed, only rewritten.

    For a carrier of density n, mobility mu and sign s, `a = n q mu/sigma(0)`
    and `b = s a mu`. If that were not exact the extension would be fitting a
    different physics from the one the rest of the program fits.
    """
    n = [3.0e19, 6.0e20, 8.0e19, 1.6e21]
    mu = [45000.0, 12000.0, 33000.0, 800.0]
    sign = [SIGN_HOLE, SIGN_HOLE, SIGN_ELECTRON, SIGN_ELECTRON]

    sxx, sxy = conductivity_tensor(FIELDS, density_to_si(n), mobility_to_si(mu), sign)
    zero = conductivity_tensor(
        np.array([0.0]), density_to_si(n), mobility_to_si(mu), sign)[0][0]

    m = mobility_to_si(mu)
    a = density_to_si(n) * 1.602176634e-19 * m / zero
    b = np.asarray(sign) * a * m

    X, Y = lorentzian.evaluate(FIELDS, a, b, m)
    assert np.allclose(X, sxx / zero, rtol=0, atol=1e-14)
    assert np.allclose(Y, sxy / zero, rtol=0, atol=1e-14)


def test_the_transform_of_an_all_hole_system_is_its_own_hall():
    """The sentence that explains the method, as an assertion.

    `X'` is what the Hall would be if every carrier were a hole. So for a
    system that really is all holes, `X'` equals `Y` exactly; for one that is
    all electrons it equals `-Y`.
    """
    a = np.array([0.6, 0.4])
    mu = np.array([2.0, 0.3])

    _, Y_holes = lorentzian.evaluate(FIELDS, a, a * mu, mu)
    Xt_holes, _ = lorentzian.transform(FIELDS, a, a * mu, mu)
    assert np.allclose(Xt_holes, Y_holes, rtol=0, atol=1e-15)

    _, Y_electrons = lorentzian.evaluate(FIELDS, a, -a * mu, mu)
    Xt_electrons, _ = lorentzian.transform(FIELDS, a, -a * mu, mu)
    assert np.allclose(Xt_electrons, -Y_electrons, rtol=0, atol=1e-15)


# ----------------------------------------------------------- packing and bounds

def test_split_and_join_are_inverses():
    a = np.array([0.5, 0.3])
    b = np.array([0.4, -0.2])
    mu = np.array([2.0, 0.5])
    back_a, back_b, back_mu = lorentzian.split(lorentzian.join(a, b, mu), 2)
    assert np.allclose(back_a, a)
    assert np.allclose(back_b, b)
    assert np.allclose(back_mu, mu)


def test_a_non_positive_mobility_is_refused():
    with pytest.raises(ValueError):
        lorentzian.join([1.0], [1.0], [0.0])


def test_a_wrongly_sized_vector_is_refused():
    with pytest.raises(ValueError):
        lorentzian.split(np.zeros(5), 2)


# ------------------------------------------------------------ sigma_xx at zero

def test_the_zero_field_value_uses_a_window_not_one_record():
    """Everything downstream divides by this, so one noisy record must not set it."""
    B = np.linspace(-2.0, 2.0, 201)
    clean = 3.0 - 0.25 * B ** 2
    spoiled = clean.copy()
    spoiled[np.argmin(np.abs(B))] += 1.0          # a single bad record at B = 0

    from_window, used = lorentzian.zero_field_value(B, spoiled, 0.5)
    assert used > 3
    assert from_window == pytest.approx(3.0, abs=0.05)
    assert abs(from_window - 3.0) < abs(spoiled[np.argmin(np.abs(B))] - 3.0)


def test_a_window_too_narrow_to_fit_falls_back_to_the_nearest_record():
    B = np.array([-1.0, 0.0, 1.0])
    value, used = lorentzian.zero_field_value(B, np.array([2.0, 5.0, 2.0]), 1e-6)
    assert used == 0
    assert value == 5.0
