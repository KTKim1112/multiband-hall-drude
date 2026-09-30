"""Research 4.8: what a residual of the size present does to the parameters.

Three claims are worth pinning, because each one is easy to get backwards and
each one changes how a reader quotes the result.

    A converged fit cannot be moved by the residual it already carries.
    The same residual, restricted to one channel, moves it by several percent.
    The condition number is the factor between the luckiest and the
    unluckiest perturbation of that same size.

The first is the reason the other two are needed: a fit gives no self-report
of its own misspecification bias, so the honest number has to come from a
counterfactual.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, fitting
from mbfit.core.units import resistivity_from_si

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data" / "synthetic_5K.csv"
CONFIG = ROOT / "configs" / "synthetic_5K.json"


@pytest.fixture(scope="module")
def reference():
    """The converged 5 K fit, with the model curve and residual it leaves."""
    config = cfg.resolve(json.loads(CONFIG.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(DATA, config)
    group = dataset.groups[0]
    fit = fitting.fit_temperature(group, config)
    sign = fitting.signs(fit.specs)
    polarity = float(config.model["hall_polarity"])
    model_xx, model_xy = fitting.model_resistivity(group.B_T, fit.params, sign, polarity)
    return dict(
        config=config,
        group=group,
        fit=fit,
        sign=sign,
        polarity=polarity,
        model_xx=model_xx,
        model_xy=model_xy,
        r_xx=group.rhoxx_uohmcm - model_xx,
        r_xy=group.rhoxy_uohmcm - model_xy,
    )


def _refit(reference, d_xx, d_xy):
    """Worst relative parameter shift when the data is the model plus delta."""
    group = dataclasses.replace(
        reference["group"],
        rhoxx_uohmcm=reference["model_xx"] + d_xx,
        rhoxy_uohmcm=reference["model_xy"] + d_xy,
    )
    fit = fitting.fit_temperature(group, reference["config"])
    ratio = fit.params_canonical / reference["fit"].params_canonical
    return float(np.max(np.abs(ratio - 1.0))), fit


# ------------------------------------------------- the residual cannot move it

@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_the_fits_own_residual_moves_nothing(reference, alpha):
    """The normal equations, as an experiment.

    A converged least-squares fit leaves a residual orthogonal to the
    Jacobian, so `model + alpha * r` returns the same parameters for every
    alpha. Research 4.8 measures at most 0.055 % over the whole range.
    """
    worst, _ = _refit(reference, alpha * reference["r_xx"], alpha * reference["r_xy"])
    assert worst < 0.002, f"alpha {alpha}: worst shift {worst:.5f}"


def test_alpha_one_reproduces_the_measurement_exactly(reference):
    """Because at alpha = 1 the synthetic data *is* the measurement."""
    group = reference["group"]
    rebuilt_xx = reference["model_xx"] + reference["r_xx"]
    rebuilt_xy = reference["model_xy"] + reference["r_xy"]
    assert np.allclose(rebuilt_xx, group.rhoxx_uohmcm, rtol=0, atol=1e-12)
    assert np.allclose(rebuilt_xy, group.rhoxy_uohmcm, rtol=0, atol=1e-12)


# -------------------------------------------- but one channel of it does move it

@pytest.mark.parametrize("channel", ["rhoxx", "rhoxy"])
def test_one_channel_of_the_same_residual_moves_it_by_percent(reference, channel):
    """Research 4.8 measures 4.6 % and 5.6 % for the two channels at 5 K.

    The contrast with the test above is the whole point. Identical size,
    identical shape, and the only difference is that the cancellation over
    the two channels has been broken.
    """
    zero = np.zeros_like(reference["r_xx"])
    d_xx = reference["r_xx"] if channel == "rhoxx" else zero
    d_xy = zero if channel == "rhoxx" else reference["r_xy"]
    worst, fit = _refit(reference, d_xx, d_xy)

    # Research 4.8 measured 4.6 % and 5.6 % on the supplied sweeps. The
    # synthetic fixture departs from a four-carrier model further than they did
    # -- 42 times the noise against their 67, but spread differently -- and the
    # same one-channel residual moves it 18 % and 20 %. The contrast the test
    # exists for is unchanged and larger: the two-channel case above stays
    # under a percent.
    assert 0.02 < worst < 0.25, f"{channel}: worst shift {worst:.4f}"
    # and it is a real solution, not a search that gave up
    assert fit.r2_rhoxx > 0.99
    assert not fit.at_bound_low.any() and not fit.at_bound_high.any()


# ------------------------------------- and the condition number says how badly

def test_the_condition_number_is_the_ratio_between_best_and_worst_direction(reference):
    """Perturb along `u_max` and along `u_min`, same size, and take the ratio.

    Research 4.8 measures 0.71 % against 56 %, a ratio of 79 against a
    condition number of 110 -- the same order, which is the claim. A tighter
    assertion would be pinning arithmetic noise rather than physics, so this
    checks the order of magnitude and the direction.
    """
    group, fit = reference["group"], reference["fit"]
    objective, scales = fitting.make_objective(group, reference["config"], reference["sign"])
    x = fitting.encode(fit.params)
    J = fitting.log_jacobian(objective, x)
    U, _, _ = np.linalg.svd(J, full_matrices=False)

    size = float(np.linalg.norm(objective(x)))
    n = int(group.in_fit_window.sum())

    def along(direction):
        d = direction / np.linalg.norm(direction) * size
        d_xx = np.zeros(group.B_T.size)
        d_xy = np.zeros(group.B_T.size)
        d_xx[group.in_fit_window] = resistivity_from_si(-d[:n] * scales[0])
        d_xy[group.in_fit_window] = resistivity_from_si(-d[n:] * scales[1])
        return _refit(reference, d_xx, d_xy)[0]

    luckiest = along(U[:, 0])
    unluckiest = along(U[:, -1])

    assert unluckiest > luckiest
    ratio = unluckiest / luckiest
    kappa = fit.condition_number
    assert 0.1 * kappa < ratio < 10.0 * kappa, (
        f"ratio {ratio:.1f} against condition number {kappa:.1f}"
    )
    # The unluckiest direction is what makes the parameters untrustworthy
    # long before the fit quality shows it.
    assert unluckiest > 0.1


def test_the_noise_floor_is_far_below_the_residual(reference):
    """Research 4.8: the measurement is 78 times better than the model at 5 K.

    Estimated from second differences, which have six times the variance of
    the noise itself when the noise is independent. If this ratio ever falls
    to order 1, the residual is noise and section 4.8 does not apply.
    """
    r = reference["r_xx"]
    d2 = np.diff(r, n=2)
    mad = float(np.median(np.abs(d2 - np.median(d2))))
    noise = mad / 0.6744897501960817 / np.sqrt(6.0)
    assert r.std() / noise > 20.0
