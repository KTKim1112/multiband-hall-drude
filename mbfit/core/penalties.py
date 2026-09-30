"""Penalties coupling one temperature to the next, and monotonic expectations.

FR-027 to FR-032, FR-052, FR-053 and NR-003. Every penalty here acts on
`log p`, so that a change from 1 to 2 and a change from 100 to 200 are
penalised equally, and on carriers put in canonical order first.

**Why canonical order.** PM-003 says exchanging two carriers of the same sign
leaves the model unchanged, so the order they were declared in carries no
information. A penalty written on `log n_e1(T_i+1) - log n_e1(T_i)` would
nonetheless assert that the carrier called `e1` at one temperature is the same
physical carrier at the next. That assertion is not in the model. Ordering by
decreasing mobility before differencing replaces an arbitrary assertion with a
stated one; ledger C9 records the price, which is that sorting is continuous
but not differentiable where two mobilities are equal.

**Why the second-order form looks the way it does.** The obvious expression,
`dbar [ (y_i+1 - y_i)/d_i+1 - (y_i - y_i-1)/d_i ]`, penalises the change in
slope rather than the curvature, and violates FR-031: on a series of constant
curvature measured every 2 K below 20 K and every 20 K above, its terms are
0.080 in the dense region and 0.800 in the sparse one, a factor of ten for
the same physics. Dividing by the mean of the two intervals is the consistent
second-derivative estimate. It gives 0.080 throughout and still reduces to
the plain second difference on an even grid.
"""

from __future__ import annotations

import numpy as np

from .canonical import canonical_permutation

ORDER_FIRST = 1
ORDER_SECOND = 2

DIRECTION_NONE = "none"
DIRECTION_INCREASE = "increase"
DIRECTION_DECREASE = "decrease"


def segment_indices(temperatures, breaks) -> np.ndarray:
    """Which segment each temperature belongs to. FR-053.

    A break at `Tb` separates the temperatures below it from those above, so
    that no penalty term spans it. A penalty crossing a phase transition
    asserts continuity where the sample provides none.
    """
    T = np.asarray(temperatures, dtype=float)
    segment = np.zeros(T.shape, dtype=int)
    for break_temperature in sorted(float(b) for b in (breaks or ())):
        segment += (T > break_temperature).astype(int)
    return segment


def canonical_rows(X_log, sign):
    """Every row of a log-parameter matrix put in canonical order. FR-052.

    Ordering by decreasing mobility is the same in the logarithm as outside
    it, so this can act on the log rows directly.
    """
    X = np.atleast_2d(np.asarray(X_log, dtype=float))
    ordered = np.empty_like(X)
    for row in range(X.shape[0]):
        permutation = canonical_permutation(X[row], sign)
        ordered[row, 0::2] = X[row, 0::2][permutation]
        ordered[row, 1::2] = X[row, 1::2][permutation]
    return ordered


def _quantity_mask(include_density, include_mobility) -> np.ndarray:
    """Which components of the flat vector a penalty touches. FR-030."""
    density = np.asarray(include_density, dtype=bool)
    mobility = np.asarray(include_mobility, dtype=bool)
    mask = np.zeros(2 * density.size, dtype=bool)
    mask[0::2] = density
    mask[1::2] = mobility
    return mask


def coupling_residual(
    X_log,
    temperatures,
    sign,
    *,
    order: int = ORDER_SECOND,
    lambda_density: float = 0.0,
    lambda_mobility: float = 0.0,
    smooth_density=None,
    smooth_mobility=None,
    breaks=(),
) -> np.ndarray:
    """The temperature coupling penalty, as residuals. FR-027 to FR-031.

    `X_log` has one row per temperature and `2N` columns. Returns an empty
    array when nothing is coupled, so a caller can concatenate it
    unconditionally.
    """
    X = canonical_rows(X_log, sign)
    T = np.asarray(temperatures, dtype=float)
    n_carriers = X.shape[1] // 2

    if smooth_density is None:
        smooth_density = np.ones(n_carriers, dtype=bool)
    if smooth_mobility is None:
        smooth_mobility = np.ones(n_carriers, dtype=bool)

    if T.size < 2:
        return np.zeros(0, dtype=float)

    spacing = np.diff(T)
    typical = float(np.median(spacing))
    segment = segment_indices(T, breaks)

    parts: list[np.ndarray] = []
    for strength, mask in (
        (float(lambda_density), _quantity_mask(smooth_density, np.zeros(n_carriers, bool))),
        (float(lambda_mobility), _quantity_mask(np.zeros(n_carriers, bool), smooth_mobility)),
    ):
        if strength <= 0.0 or not np.any(mask):
            continue
        Y = X[:, mask]

        if order == ORDER_FIRST:
            # The discretisation of a penalty on the derivative: the squares
            # sum to lambda * dbar * the integral of (dy/dT)^2. A gap twice as
            # wide therefore allows sqrt(2) times the change, not twice.
            for i in range(1, T.size):
                if segment[i] != segment[i - 1]:
                    continue
                width = max(spacing[i - 1], 1e-12)
                parts.append(
                    np.sqrt(strength) * np.sqrt(typical / width) * (Y[i] - Y[i - 1])
                )
        elif order == ORDER_SECOND:
            for i in range(1, T.size - 1):
                if segment[i - 1] != segment[i] or segment[i] != segment[i + 1]:
                    continue
                lower = max(spacing[i - 1], 1e-12)
                upper = max(spacing[i], 1e-12)
                curvature = (
                    2.0
                    * ((Y[i + 1] - Y[i]) / upper - (Y[i] - Y[i - 1]) / lower)
                    / (lower + upper)
                )
                parts.append(np.sqrt(strength) * typical**2 * curvature)
        else:
            raise ValueError(f"smoothing order must be {ORDER_FIRST} or {ORDER_SECOND}")

    return np.concatenate(parts) if parts else np.zeros(0, dtype=float)


def monotonic_residual(
    X_log,
    temperatures,
    sign,
    *,
    strength: float = 0.0,
    density_directions=None,
    mobility_directions=None,
    breaks=(),
) -> np.ndarray:
    """The monotonic expectation, as a penalty. FR-032.

    One-sided: a step in the expected direction costs nothing, a step against
    it costs. That is what makes it a prior a sufficiently insistent data set
    can overcome, rather than a constraint it cannot.
    """
    X = canonical_rows(X_log, sign)
    T = np.asarray(temperatures, dtype=float)
    n_carriers = X.shape[1] // 2
    if T.size < 2 or strength <= 0.0:
        return np.zeros(0, dtype=float)

    density_directions = density_directions or [DIRECTION_NONE] * n_carriers
    mobility_directions = mobility_directions or [DIRECTION_NONE] * n_carriers
    segment = segment_indices(T, breaks)
    same_segment = segment[1:] == segment[:-1]

    parts: list[np.ndarray] = []
    for offset, directions in ((0, density_directions), (1, mobility_directions)):
        for carrier_index, direction in enumerate(directions):
            if direction == DIRECTION_NONE:
                continue
            column = X[:, 2 * carrier_index + offset]
            steps = np.diff(column)[same_segment]
            if direction == DIRECTION_INCREASE:
                offending = np.minimum(steps, 0.0)
            elif direction == DIRECTION_DECREASE:
                offending = np.maximum(steps, 0.0)
            else:
                raise ValueError(f"unknown monotonic direction: {direction!r}")
            parts.append(np.sqrt(strength) * offending)

    return np.concatenate(parts) if parts else np.zeros(0, dtype=float)


def order_changes(X_log, sign):
    """Where the canonical order changes along a series. FR-047.

    Returns the indices `i` at which the order between temperature `i` and
    `i + 1` differs. PM-003 makes such an exchange free of cost, so it must be
    reported next to any jump rather than instead of it.
    """
    X = np.atleast_2d(np.asarray(X_log, dtype=float))
    changed = []
    previous = canonical_permutation(X[0], sign)
    for row in range(1, X.shape[0]):
        current = canonical_permutation(X[row], sign)
        if np.any(current != previous):
            changed.append(row - 1)
        previous = current
    return changed
