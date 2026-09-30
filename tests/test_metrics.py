"""FR-020, FR-040, FR-055, AC-007, AC-010."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mbfit.core.metrics import (
    condition_number,
    r_squared,
    rmse,
    robust_scale,
    runs_test_z,
    singular_values,
)


def test_r_squared_is_one_for_a_perfect_fit_and_zero_for_the_mean():
    y = np.array([1.0, 2.0, 4.0, 8.0])
    assert r_squared(y, y) == pytest.approx(1.0)
    assert r_squared(y, np.full_like(y, y.mean())) == pytest.approx(0.0)


def test_r_squared_is_not_a_number_when_the_measurement_has_no_variance():
    flat = np.full(5, 3.0)
    assert math.isnan(r_squared(flat, flat))


def test_rmse_is_in_the_units_of_its_arguments():
    y = np.zeros(4)
    assert rmse(y, np.full(4, 2.0)) == pytest.approx(2.0)


# ------------------------------------------------------------ robust scale

def test_robust_scale_is_the_median_absolute_value():
    assert robust_scale([-3.0, 1.0, 2.0, 100.0]) == pytest.approx(2.5)


def test_robust_scale_ignores_a_few_bad_records():
    clean = np.linspace(-1.0, 1.0, 101)
    dirtied = clean.copy()
    dirtied[:3] = 1e9
    assert robust_scale(dirtied) == pytest.approx(robust_scale(clean), rel=0.05)


def test_robust_scale_falls_back_and_never_returns_zero():
    assert robust_scale(np.zeros(10)) == 1.0            # median 0, spread 0
    assert robust_scale([]) == 1.0
    alternating = np.array([-1.0, 1.0, -1.0, 1.0])      # median of |y| is 1
    assert robust_scale(alternating) == pytest.approx(1.0)


def test_normalising_by_the_scale_is_invariant_to_rescaling_a_channel():
    """Research 5.4: it equalises signal, and this is what that means.

    An earlier draft claimed a narrow sweep over-weights the Hall channel. It
    does not, because the residuals and the scale shrink together.
    """
    measured = np.linspace(-1.0, 1.0, 51)
    fitted = measured * 1.02
    residual = (fitted - measured) / robust_scale(measured)
    for factor in (1e-6, 1e3):
        scaled = residual * 0 + (fitted * factor - measured * factor) / robust_scale(
            measured * factor
        )
        assert np.allclose(scaled, residual, rtol=1e-12)


# ---------------------------------------------------------------- runs test

def test_runs_test_is_near_zero_for_scatter():
    generator = np.random.default_rng(0)
    scores = [runs_test_z(generator.normal(size=400)) for _ in range(20)]
    assert abs(float(np.mean(scores))) < 1.0


def test_runs_test_is_strongly_negative_for_a_structured_residual():
    """Too few runs. A smooth departure keeps its sign for long stretches."""
    field = np.linspace(-9.0, 9.0, 361)
    structured = np.sin(field * np.pi / 9.0)  # three sign changes in 361 points
    assert runs_test_z(structured) < -15.0


def test_runs_test_is_strongly_positive_for_an_alternating_residual():
    """Too many runs is also a failure of randomness, in the other direction."""
    alternating = np.where(np.arange(200) % 2 == 0, 1.0, -1.0)
    assert runs_test_z(alternating) > 10.0


def test_runs_test_handles_a_residual_of_constant_sign_and_a_tiny_one():
    assert runs_test_z(np.ones(50)) == float("-inf")
    assert math.isnan(runs_test_z([1.0]))
    assert math.isnan(runs_test_z([0.0, 0.0, 0.0]))


def test_runs_test_does_not_depend_on_the_sampling_density():
    """Why AC-007 uses this and not the lag-1 autocorrelation. Research 4.6.

    The same structured departure, sampled twice as finely, scores similarly
    on the runs test. Autocorrelation would climb towards 1.
    """
    coarse = np.sin(np.linspace(-9.0, 9.0, 181) * np.pi / 9.0)
    fine = np.sin(np.linspace(-9.0, 9.0, 1441) * np.pi / 9.0)
    coarse_correlation = float(np.corrcoef(coarse[:-1], coarse[1:])[0, 1])
    fine_correlation = float(np.corrcoef(fine[:-1], fine[1:])[0, 1])
    assert fine_correlation > coarse_correlation
    assert runs_test_z(coarse) < -10.0
    assert runs_test_z(fine) < -10.0


# -------------------------------------------------------------- conditioning

def test_condition_number_of_a_well_scaled_matrix_is_small():
    assert condition_number(np.eye(4)) == pytest.approx(1.0)


def test_condition_number_grows_as_two_columns_become_parallel():
    """Two carriers that cannot be told apart make two columns alike."""
    previous = 0.0
    for gap in (1e-1, 1e-3, 1e-6):
        jacobian = np.array([[1.0, 1.0], [0.0, gap], [1.0, 1.0 + gap]])
        current = condition_number(jacobian)
        assert current > previous
        previous = current
    assert previous > 1e5


def test_condition_number_is_infinite_only_for_an_exactly_zero_direction():
    """A duplicated column is enormous but finite; a dead one is infinite.

    Worth separating. Floating point rarely hands back an exact zero, so the
    diagnostic has to be a threshold on a large number rather than a test for
    infinity, and AC-010 is written that way.
    """
    duplicated = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
    assert condition_number(duplicated) > 1e12
    assert math.isfinite(condition_number(duplicated))

    dead_direction = np.array([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    assert condition_number(dead_direction) == float("inf")


def test_singular_values_come_back_largest_first():
    values = singular_values(np.diag([3.0, 7.0, 1.0]))
    assert np.all(np.diff(values) <= 0.0)
    assert values[0] == pytest.approx(7.0)


def test_singular_values_rejects_a_vector():
    with pytest.raises(ValueError):
        singular_values(np.arange(5.0))
