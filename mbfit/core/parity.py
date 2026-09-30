"""How much of each channel has the wrong parity in `B`. FR-065.

Onsager requires the longitudinal channel to be even in field and the Hall
channel odd. A real measurement is neither, because the transverse contacts
are never exactly opposite one another: a fraction of the longitudinal voltage
appears in the Hall channel and does not change sign with the field.

Symmetrising removes it, and FR-008 and FR-009 do. What symmetrising does not
do is say **how much was removed**, and that number is the one piece of
evidence about contact geometry that a magnetotransport sweep carries. A
violation of a few parts in a hundred is ordinary; a large one says the
contacts or the sample are not what the analysis assumes, and no amount of
fitting afterwards will recover from it.

Measured before symmetrisation, or it measures nothing at all.
"""

from __future__ import annotations

import numpy as np

PARITY_EVEN = +1
PARITY_ODD = -1


def _paired(B_T, y, tolerance: float):
    """Values at `+B` and `-B`, for the fields present in both polarities."""
    B = np.asarray(B_T, dtype=float)
    values = np.asarray(y, dtype=float)
    if B.shape != values.shape:
        raise ValueError("field and values must have the same shape")

    positive = B > tolerance
    if not np.any(positive):
        return np.zeros(0), np.zeros(0)

    here, mirrored = [], []
    for field, value in zip(B[positive], values[positive]):
        match = np.abs(B + field) <= tolerance
        if np.any(match):
            here.append(value)
            mirrored.append(float(np.mean(values[match])))
    return np.asarray(here, dtype=float), np.asarray(mirrored, dtype=float)


def violation(B_T, y, parity: int, tolerance: float = 1e-9):
    """Norm of the wrong-parity part over the norm of the right-parity part.

    Returns `None` when the sweep carries only one polarity, which FR-066
    requires to be reported as unmeasured rather than as zero. Returns `0.0`
    for a sweep that is already exactly symmetric, which is what the supplied
    reference data is.
    """
    if parity not in (PARITY_EVEN, PARITY_ODD):
        raise ValueError("parity must be +1 (even) or -1 (odd)")

    here, mirrored = _paired(B_T, y, tolerance)
    if here.size == 0:
        return None

    # For an even channel the wanted part is the half-sum and the unwanted the
    # half-difference; for an odd channel the two exchange roles.
    half_sum = 0.5 * (here + mirrored)
    half_difference = 0.5 * (here - mirrored)
    wanted, unwanted = (
        (half_sum, half_difference) if parity == PARITY_EVEN
        else (half_difference, half_sum)
    )

    scale = float(np.linalg.norm(wanted))
    if scale == 0.0:
        return float("inf") if np.linalg.norm(unwanted) > 0.0 else 0.0
    return float(np.linalg.norm(unwanted) / scale)


def both_polarities(B_T, tolerance: float = 1e-9) -> bool:
    """Whether the sweep carries fields of both signs. FR-066."""
    B = np.asarray(B_T, dtype=float)
    return bool(np.any(B > tolerance) and np.any(B < -tolerance))
