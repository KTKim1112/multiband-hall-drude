"""PM-003, FR-047 and FR-052: carrier exchange, and what follows from it."""

from __future__ import annotations

import numpy as np

from mbfit.core.canonical import (
    canonical_permutation,
    canonicalise,
    join_parameters,
    order_changed,
    split_parameters,
)
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si

FIELDS = np.array([-9.0, -1.0, 0.5, 4.0, 9.0])

# Two electrons and two holes, mobilities deliberately out of canonical order.
SIGN = [SIGN_ELECTRON, SIGN_ELECTRON, SIGN_HOLE, SIGN_HOLE]
PARAMS = join_parameters(
    density_to_si([8.9e20, 1.5e19, 2.0e21, 3.6e18]),
    mobility_to_si([500.0, 19000.0, 1100.0, 20000.0]),
)


def _model(params, sign):
    n, mu = split_parameters(params)
    return resistivity(FIELDS, n, mu, sign)


def test_PM003_exchanging_same_sign_carriers_leaves_the_model_unchanged():
    """The symmetry every later decision about labels rests on."""
    swapped = PARAMS.copy()
    swapped[[0, 1, 2, 3]] = PARAMS[[2, 3, 0, 1]]  # exchange the two electrons
    before = _model(PARAMS, SIGN)
    after = _model(swapped, SIGN)
    assert np.allclose(before[0], after[0], rtol=1e-15, atol=0.0)
    assert np.allclose(before[1], after[1], rtol=1e-15, atol=0.0)


def test_exchanging_carriers_of_opposite_sign_does_change_the_model():
    """The symmetry is of same-sign carriers only, and the test says so."""
    n, mu = split_parameters(PARAMS)
    flipped_sign = [SIGN_HOLE, SIGN_HOLE, SIGN_ELECTRON, SIGN_ELECTRON]
    _, hall_before = resistivity(FIELDS, n, mu, SIGN)
    _, hall_after = resistivity(FIELDS, n, mu, flipped_sign)
    assert np.max(np.abs(hall_before - hall_after)) > 0.0


def test_canonical_order_is_decreasing_mobility_within_each_sign():
    ordered = canonicalise(PARAMS, SIGN)
    _, mu = split_parameters(ordered)
    sign = np.asarray(SIGN, dtype=float)
    for one_sign in (SIGN_ELECTRON, SIGN_HOLE):
        group = mu[sign == one_sign]
        assert np.all(np.diff(group) <= 0.0)


def test_canonicalisation_keeps_each_sign_in_its_own_positions():
    """Electrons stay in electron slots; only the assignment within moves."""
    permutation = canonical_permutation(PARAMS, SIGN)
    sign = np.asarray(SIGN, dtype=float)
    assert np.array_equal(sign[permutation], sign)


def test_canonicalisation_does_not_change_the_model():
    before = _model(PARAMS, SIGN)
    after = _model(canonicalise(PARAMS, SIGN), SIGN)
    assert np.allclose(before[0], after[0], rtol=1e-15, atol=0.0)
    assert np.allclose(before[1], after[1], rtol=1e-15, atol=0.0)


def test_canonicalisation_is_idempotent():
    once = canonicalise(PARAMS, SIGN)
    assert np.array_equal(canonicalise(once, SIGN), once)


def test_FR047_detects_a_crossing_and_not_a_mere_change_of_value():
    """What FR-047 reports is the declared-to-canonical mapping changing.

    Between two temperatures, the carrier declared `e1` being the faster one
    at the first and the slower one at the second is the relabelling PM-003
    makes free, and is the commonest cause of what looks like a jump.
    """
    warm = join_parameters(
        [1.0e25, 1.0e26, 1.0e25, 1.0e26], [19000.0, 500.0, 20000.0, 1100.0]
    )
    cooler = join_parameters(
        [1.1e25, 1.1e26, 1.1e25, 1.1e26], [18000.0, 600.0, 19000.0, 1200.0]
    )
    assert order_changed(warm, cooler, SIGN) is False

    crossed = join_parameters(
        [1.1e25, 1.1e26, 1.1e25, 1.1e26], [400.0, 17000.0, 19000.0, 1200.0]
    )
    assert order_changed(warm, crossed, SIGN) is True


def test_an_exact_tie_keeps_the_declared_order():
    """Sorting is continuous but not differentiable at a tie, per ledger C9.

    A stable sort at least makes the behaviour there predictable rather than
    dependent on the sort routine.
    """
    tied = join_parameters([1e25, 2e25, 1e25, 2e25], [5.0, 5.0, 3.0, 3.0])
    assert np.array_equal(canonical_permutation(tied, SIGN), np.arange(4))
