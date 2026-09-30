"""Splitting the normalised conductivities into hole and electron parts.

FR-070 and FR-071. This is the step the whole feature turns on.

`sigma_xx` is even in field and carries no sign information: an electron and a
hole of the same density and mobility contribute identically to it. `sigma_xy`
is odd and carries the sign. The Kramers-Kronig transform of `lorentzian.py`
links the two, and that link is what lets the two carrier types be told apart:

    X' = Y^p + Y^n          what the Hall would be if every carrier were a hole
    Y' = -X^p + X^n

Together with `X = X^p + X^n` and `Y = Y^p - Y^n`, four unknowns in four
equations:

    X^p = (X - Y') / 2      X^n = (X + Y') / 2
    Y^p = (Y + X') / 2      Y^n = (X' - Y) / 2

**Sign convention, stated once and used everywhere.** All four returned parts
are non-negative *amplitudes*. The measured Hall is `Y = Y^p - Y^n`, with the
electron sign written out rather than hidden inside `Y^n`. The published method
this follows writes `Y = Y^p + Y^n` with a negative `Y^n`; the two differ only
in bookkeeping, and this one is chosen because it makes the hole and electron
inverse problems share one kernel instead of two that differ by a sign.

Research 003 section 2.3 records these identities verified to `1e-16` against
`drude.py` on a four-carrier mixture.
"""

from __future__ import annotations

import numpy as np


def separate(X, Y, X_transformed, Y_transformed):
    """The four parts, as non-negative amplitudes.

    Returns `(X_hole, X_electron, Y_hole, Y_electron)`. Nothing is clipped
    here: a negative part is a real signal that the assumptions upstream have
    failed, and `negative_fraction` measures it rather than hiding it.
    """
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    Xt = np.asarray(X_transformed, dtype=float)
    Yt = np.asarray(Y_transformed, dtype=float)
    if not (X.shape == Y.shape == Xt.shape == Yt.shape):
        raise ValueError("all four inputs must have the same shape")

    return (
        0.5 * (X - Yt),
        0.5 * (X + Yt),
        0.5 * (Y + Xt),
        0.5 * (Xt - Y),
    )


def negative_fraction(part, B_T=None) -> float:
    """How much of a separated part has the wrong sign, as a norm ratio.

    A separated longitudinal part is a conductivity and cannot be negative
    anywhere. A separated Hall part is *odd* in field, so it is negative for
    negative field by construction; what it cannot do is change sign relative
    to the field. Passing `B_T` selects the second reading, by measuring the
    part divided by the field instead of the part itself.

    Either way, when the sign is wrong the Lorentzian extension upstream has
    failed to describe the data, or the field range does not constrain a
    mobility the extension needed. The quantity returned is
    `||wrong-signed part|| / ||part||`, zero for a clean separation and of
    order one for a broken one.

    Measured rather than repaired. Clipping a negative excursion to zero would
    hide exactly the case a reader has to be told about.
    """
    p = np.asarray(part, dtype=float)
    if B_T is not None:
        B = np.asarray(B_T, dtype=float)
        if B.shape != p.shape:
            raise ValueError("field and part must have the same shape")
        usable = B != 0.0
        p = p[usable] / B[usable]
    scale = float(np.linalg.norm(p))
    if scale == 0.0:
        return 0.0
    return float(np.linalg.norm(np.minimum(p, 0.0)) / scale)


def recombine(X_hole, X_electron, Y_hole, Y_electron):
    """Put the parts back together, for checking that they add up. AC-023."""
    return (
        np.asarray(X_hole, dtype=float) + np.asarray(X_electron, dtype=float),
        np.asarray(Y_hole, dtype=float) - np.asarray(Y_electron, dtype=float),
    )
