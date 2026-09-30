"""FR-082 and FR-087 amended -- past the spectrum's bound, and fit quality on the scale of the noise.

Research 004 section 6.2. At 70 to 90 K the spectrum proposed one carrier of
each sign, the search never tried 2h+2e, and a 1h+1e whose residual was 53 to
58 times the noise was graded A while 100 and 120 K, followed to 7 and 11 times
the noise, were graded C. Two things were missing: a search allowed past the
bound, and a measure of fit that does not depend on how much the curve varies.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import workflow
from mbfit.core.metrics import noise_second_difference


def test_the_noise_of_a_smooth_dense_sweep_is_recovered():
    rng = np.random.default_rng(7)
    B = np.linspace(-9.0, 9.0, 361)
    for sigma in (1e-3, 1e-2):
        curve = 2.0 + 0.4 * B ** 2 / (1.0 + 0.05 * B ** 2)
        noisy = curve + rng.normal(0.0, sigma, B.size)
        assert noise_second_difference(noisy) == pytest.approx(sigma, rel=0.15)


def test_a_short_sweep_has_no_noise_estimate():
    assert np.isnan(noise_second_difference([1.0, 2.0, 3.0]))


def test_growth_is_one_step_of_either_sign_or_both():
    assert workflow.growth_of(1, 1, {(1, 1)}, 4) == [(2, 1), (1, 2), (2, 2)]


def test_growth_skips_what_was_fitted_and_respects_the_limit():
    tried = {(1, 1), (2, 1), (1, 2)}
    assert workflow.growth_of(1, 1, tried, 4) == [(2, 2)]
    assert workflow.growth_of(4, 3, set(), 4) == [(4, 4)]
    assert workflow.growth_of(4, 4, set(), 4) == []


def test_the_larger_combination_is_chosen_only_when_it_fits_better_by_the_factor():
    """FR-085 drives the growth: no new threshold. The 80 K numbers."""
    settings = {"residual_factor": 1.25, "spread_max": 0.01, "share_min": 0.001}

    def candidate(n_hole, n_electron, rmse, spread=1e-6, share=0.1):
        return workflow.Candidate(
            n_hole=n_hole, n_electron=n_electron, rmse_rhoxx=rmse, rmse_rhoxy=rmse / 5,
            r2_rhoxx=0.99, r2_rhoxy=0.999, condition_number=1e3, spread=spread,
            weakest_share=share, at_bound=False, expired=False, n_starts=12,
            seconds=1.0, params=np.array([1.0]), specs=("x",))

    small = candidate(1, 1, 0.0414)
    large = candidate(2, 2, 0.0079, share=0.0085)
    chosen, failed, _ = workflow.select([small, large], settings)
    assert chosen.label == "2h+2e" and failed == []

    barely = candidate(2, 2, 0.036)
    chosen, _, _ = workflow.select([small, barely], settings)
    assert chosen.label == "1h+1e"


def _growth_candidate(n_hole, n_electron, rmse):
    return workflow.Candidate(
        n_hole=n_hole, n_electron=n_electron, rmse_rhoxx=rmse, rmse_rhoxy=rmse / 5,
        r2_rhoxx=0.9, r2_rhoxy=0.999, condition_number=1e4, spread=1e-6,
        weakest_share=0.1, at_bound=False, expired=False, n_starts=12,
        seconds=1.0, params=np.array([1.0]), specs=("x",))


def test_growth_moves_only_to_a_better_fit():
    """FR-082. At 100 K a passing 1h+2e with a larger residual replaced a 1h+1e
    that had failed the bound gate; growing the count is for fitting better."""
    settings = {"residual_factor": 1.25}
    one = _growth_candidate(1, 1, 0.0095)
    worse = _growth_candidate(1, 2, 0.0122)
    better = _growth_candidate(2, 2, 0.0050)
    close = _growth_candidate(2, 2, 0.0080)
    assert not workflow.grows_the_fit(one, worse, settings)
    assert not workflow.grows_the_fit(one, close, settings)
    assert workflow.grows_the_fit(one, better, settings)
    assert not workflow.grows_the_fit(better, one, settings)
