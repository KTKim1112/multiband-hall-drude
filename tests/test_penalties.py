"""FR-027 to FR-032, FR-052 and FR-053: the penalties, on their own.

The formulas rather than the fits. A penalty tested only through a fit is a
penalty whose bugs hide in the optimiser.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit.core import penalties
from mbfit.core.canonical import join_parameters
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE

SIGN_ONE = np.array([SIGN_ELECTRON])
SIGN_TWO = np.array([SIGN_ELECTRON, SIGN_HOLE])


def series(temperatures, log_density, log_mobility=None):
    """A log-parameter matrix for one carrier, one row per temperature."""
    log_density = np.asarray(log_density, dtype=float)
    if log_mobility is None:
        log_mobility = np.zeros_like(log_density)
    return np.column_stack([log_density, np.asarray(log_mobility, dtype=float)])


# ------------------------------------------------------- FR-027, switched off

def test_FR027_nothing_is_returned_when_nothing_is_coupled():
    T = np.array([5.0, 10.0, 15.0])
    X = series(T, [1.0, 2.0, 5.0])
    assert penalties.coupling_residual(X, T, SIGN_ONE).size == 0
    assert penalties.coupling_residual(
        X, T, SIGN_ONE, lambda_density=0.0, lambda_mobility=0.0
    ).size == 0


# ------------------------------------------------ FR-031, the corrected form

def _second_order_terms(T, y, strength=1.0):
    X = series(T, y)
    return penalties.coupling_residual(
        X, T, SIGN_ONE, order=2, lambda_density=strength
    )


def test_FR031_constant_curvature_costs_the_same_at_every_spacing():
    """The scenario FR-031 names: 2 K below 20 K, 20 K above.

    The form this replaced gave 0.080 in the dense region and 0.800 in the
    sparse one for the same physical curvature, a factor of ten.
    """
    T = np.concatenate([np.arange(0.0, 21.0, 2.0), np.arange(40.0, 161.0, 20.0)])
    terms = _second_order_terms(T, 0.01 * T**2)
    assert np.ptp(terms) < 1e-12
    assert terms[0] == pytest.approx(0.08, rel=1e-9)


def test_FR031_a_straight_line_costs_nothing_at_any_spacing():
    """Second order penalises curvature, and a trend has none."""
    T = np.concatenate([np.arange(0.0, 21.0, 2.0), np.arange(40.0, 161.0, 20.0)])
    assert np.max(np.abs(_second_order_terms(T, 0.5 * T))) < 1e-12


def test_both_orders_reduce_to_plain_differences_on_an_even_grid():
    T = np.arange(0.0, 21.0, 2.0)
    y = 0.01 * T**2
    X = series(T, y)

    first = penalties.coupling_residual(X, T, SIGN_ONE, order=1, lambda_density=1.0)
    assert np.allclose(first, np.diff(y))

    second = penalties.coupling_residual(X, T, SIGN_ONE, order=2, lambda_density=1.0)
    assert np.allclose(second, y[2:] - 2 * y[1:-1] + y[:-2])


def test_the_first_order_term_is_the_integral_of_the_squared_derivative():
    """Its square sums to lambda * dbar * integral (dy/dT)^2. Research 5.5."""
    T = np.concatenate([np.arange(0.0, 21.0, 2.0), np.arange(40.0, 161.0, 20.0)])
    slope = 0.5
    X = series(T, slope * T)
    terms = penalties.coupling_residual(X, T, SIGN_ONE, order=1, lambda_density=1.0)
    typical = float(np.median(np.diff(T)))
    expected = typical * slope**2 * (T[-1] - T[0])
    assert float(np.sum(terms**2)) == pytest.approx(expected, rel=1e-12)


def test_an_unknown_order_is_refused():
    T = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        penalties.coupling_residual(series(T, T), T, SIGN_ONE, order=3, lambda_density=1.0)


# ------------------------------------------------------------------- FR-028

def test_FR028_the_two_strengths_act_independently():
    T = np.array([0.0, 1.0, 2.0])
    X = series(T, [0.0, 1.0, 4.0], [0.0, 2.0, 8.0])
    only_density = penalties.coupling_residual(X, T, SIGN_ONE, order=2, lambda_density=1.0)
    only_mobility = penalties.coupling_residual(X, T, SIGN_ONE, order=2, lambda_mobility=1.0)
    both = penalties.coupling_residual(
        X, T, SIGN_ONE, order=2, lambda_density=1.0, lambda_mobility=1.0
    )
    assert only_density.size == only_mobility.size == 1
    assert both.size == 2
    assert only_mobility[0] == pytest.approx(2.0 * only_density[0])


# ------------------------------------------------------------------- FR-030

def test_FR030_a_carrier_can_be_left_out_of_the_coupling():
    T = np.array([0.0, 1.0, 2.0])
    X = np.column_stack([
        [0.0, 1.0, 4.0], [0.0, 0.0, 0.0],   # carrier 0
        [0.0, 2.0, 8.0], [0.0, 0.0, 0.0],   # carrier 1
    ])
    both = penalties.coupling_residual(X, T, SIGN_TWO, order=2, lambda_density=1.0)
    first_only = penalties.coupling_residual(
        X, T, SIGN_TWO, order=2, lambda_density=1.0, smooth_density=[True, False]
    )
    assert both.size == 2
    assert first_only.size == 1


# ------------------------------------------------------------------- FR-052

def test_FR052_the_penalty_does_not_depend_on_the_declared_order():
    """PM-003 makes the declared order meaningless, so the penalty must too.

    Two rows describing the same physical solution, one of them with the two
    electrons written the other way round, must cost the same.
    """
    T = np.array([0.0, 1.0, 2.0])
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    as_declared = np.array([
        [np.log(1e19), np.log(9000.0), np.log(1e20), np.log(400.0)],
        [np.log(2e19), np.log(8000.0), np.log(2e20), np.log(500.0)],
        [np.log(3e19), np.log(7000.0), np.log(3e20), np.log(600.0)],
    ])
    relabelled = as_declared.copy()
    relabelled[1] = as_declared[1][[2, 3, 0, 1]]   # swap the two electrons

    plain = penalties.coupling_residual(
        as_declared, T, sign, order=2, lambda_density=1.0, lambda_mobility=1.0
    )
    swapped = penalties.coupling_residual(
        relabelled, T, sign, order=2, lambda_density=1.0, lambda_mobility=1.0
    )
    assert np.allclose(plain, swapped)


def test_order_changes_are_reported_where_they_happen():
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    rows = np.array([
        [np.log(1e19), np.log(9000.0), np.log(1e20), np.log(400.0)],
        [np.log(1e19), np.log(9000.0), np.log(1e20), np.log(400.0)],
        [np.log(1e19), np.log(300.0), np.log(1e20), np.log(9000.0)],  # crossed
    ])
    assert penalties.order_changes(rows, sign) == [1]


# ------------------------------------------------------------------- FR-053

def test_FR053_no_penalty_term_spans_a_declared_break():
    T = np.array([0.0, 10.0, 20.0, 30.0, 40.0])
    X = series(T, [0.0, 1.0, 4.0, 9.0, 16.0])

    whole = penalties.coupling_residual(X, T, SIGN_ONE, order=2, lambda_density=1.0)
    cut = penalties.coupling_residual(
        X, T, SIGN_ONE, order=2, lambda_density=1.0, breaks=[25.0]
    )
    assert whole.size == 3      # terms centred on 10, 20 and 30
    assert cut.size == 1        # only the one centred on 10 survives


def test_FR053_a_break_between_every_pair_removes_the_coupling_entirely():
    T = np.array([0.0, 10.0, 20.0])
    X = series(T, [0.0, 5.0, 1.0])
    cut = penalties.coupling_residual(
        X, T, SIGN_ONE, order=1, lambda_density=1.0, breaks=[5.0, 15.0]
    )
    assert cut.size == 0


def test_segments_are_numbered_in_order():
    T = np.array([1.0, 5.0, 9.0, 30.0, 50.0])
    assert list(penalties.segment_indices(T, [10.0, 40.0])) == [0, 0, 0, 1, 2]
    assert list(penalties.segment_indices(T, [])) == [0, 0, 0, 0, 0]


# ------------------------------------------------------------------- FR-032

def test_FR032_the_monotonic_prior_is_one_sided():
    """A step the expected way costs nothing; a step against it costs."""
    T = np.array([0.0, 1.0, 2.0])
    rising = series(T, [0.0, 1.0, 2.0])
    falling = series(T, [2.0, 1.0, 0.0])

    expect_increase = dict(strength=4.0, density_directions=["increase"])
    assert np.allclose(penalties.monotonic_residual(rising, T, SIGN_ONE, **expect_increase), 0.0)
    against = penalties.monotonic_residual(falling, T, SIGN_ONE, **expect_increase)
    assert np.allclose(against, [-2.0, -2.0])       # sqrt(4) * (-1) each step


def test_FR032_a_direction_of_none_costs_nothing():
    T = np.array([0.0, 1.0, 2.0])
    X = series(T, [5.0, 0.0, 5.0])
    assert penalties.monotonic_residual(
        X, T, SIGN_ONE, strength=10.0, density_directions=["none"]
    ).size == 0


def test_FR032_an_unknown_direction_is_refused():
    T = np.array([0.0, 1.0])
    with pytest.raises(ValueError):
        penalties.monotonic_residual(
            series(T, [0.0, 1.0]), T, SIGN_ONE, strength=1.0, density_directions=["upward"]
        )


def test_the_monotonic_prior_also_respects_a_break():
    T = np.array([0.0, 10.0, 20.0])
    falling = series(T, [2.0, 1.0, 0.0])
    cut = penalties.monotonic_residual(
        falling, T, SIGN_ONE, strength=4.0, density_directions=["increase"], breaks=[5.0]
    )
    assert cut.size == 1


# --------------------------------------------------------------- housekeeping

def test_a_single_temperature_couples_to_nothing():
    T = np.array([5.0])
    X = series(T, [1.0])
    assert penalties.coupling_residual(X, T, SIGN_ONE, lambda_density=1.0).size == 0
    assert penalties.monotonic_residual(
        X, T, SIGN_ONE, strength=1.0, density_directions=["increase"]
    ).size == 0


def test_canonical_rows_orders_every_row_and_leaves_the_signs_in_place():
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON, SIGN_HOLE, SIGN_HOLE])
    rows = np.log(np.array([
        join_parameters([1e19, 1e20, 1e19, 1e20], [400.0, 9000.0, 300.0, 8000.0]),
        join_parameters([1e19, 1e20, 1e19, 1e20], [9000.0, 400.0, 8000.0, 300.0]),
    ]))
    ordered = penalties.canonical_rows(rows, sign)
    for row in ordered:
        assert row[1] > row[3]      # electrons, decreasing mobility
        assert row[5] > row[7]      # holes, likewise
