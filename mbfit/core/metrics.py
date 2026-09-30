"""Fit quality, channel normalisation, and residual structure.

Everything here takes arrays and returns numbers. Nothing knows what a
temperature or a file is.
"""

from __future__ import annotations

import numpy as np


def r_squared(measured, fitted) -> float:
    """Coefficient of determination, `1 - SSE / SST`.

    Returns NaN when the measurement has no variance, since the quantity is
    then undefined rather than perfect.
    """
    y = np.asarray(measured, dtype=float)
    f = np.asarray(fitted, dtype=float)
    sse = float(np.sum((y - f) ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    if sst == 0.0:
        return float("nan")
    return 1.0 - sse / sst


def rmse(measured, fitted) -> float:
    """Root-mean-square residual, in the units of the arguments."""
    y = np.asarray(measured, dtype=float)
    f = np.asarray(fitted, dtype=float)
    return float(np.sqrt(np.mean((y - f) ** 2)))


def robust_scale(values) -> float:
    """The scale a channel is divided by before comparison. FR-020.

    The median of the absolute values, which a few bad records cannot move.
    Where that is zero the standard deviation is used, and where that is zero
    the scale is 1, so the function never returns something a caller would
    divide by and get infinity.

    Research 5.4 records what this does and does not do. It makes the
    comparison invariant to the units and the overall size of a channel -- it
    equalises *signal*, not information. A channel whose signal is small
    against its own noise is still weighted as though its residuals carried as
    much, and nothing here detects that.
    """
    y = np.asarray(values, dtype=float)
    if y.size == 0:
        return 1.0
    median_absolute = float(np.median(np.abs(y)))
    if median_absolute > 0.0:
        return median_absolute
    spread = float(np.std(y))
    return spread if spread > 0.0 else 1.0


def noise_second_difference(y) -> float:
    """Measurement noise of a densely sampled, smooth sweep.

    `std(y[i-1] - 2 y[i] + y[i+1]) / sqrt(6)`: white noise of standard deviation
    `s` gives the second difference a variance of `6 s^2`, and a smooth curve
    sampled as densely as a field sweep contributes little to it. Research 004
    section 6.2 uses it to put a fit's residual on the scale of the measurement
    rather than of the curve's own variation, which is what `R^2` does and why
    `R^2` ranked a sweep with `0.24 %` magnetoresistance below one the model
    visibly misses. If the data were smoothed before export this reads low, so
    the ratio it makes is for comparing sweeps and combinations, not an
    absolute pass mark. Returns NaN with fewer than five points.
    """
    values = np.asarray(y, dtype=float)
    if values.size < 5:
        return float("nan")
    second = values[:-2] - 2.0 * values[1:-1] + values[2:]
    return float(np.std(second) / np.sqrt(6.0))


def runs_test_z(residual) -> float:
    """Wald-Wolfowitz runs test on the sign sequence of a residual. AC-007.

    The residual is taken in the order given, which for this program means
    ordered by field. Returns the standardised score

        Z = (R - mu) / sigma,   mu = 2 n+ n- / n + 1

    where `R` is the number of runs of constant sign. A residual that is
    scatter scores near zero; one that keeps systematic structure has too few
    runs and scores strongly negative. Zeros are dropped, being neither sign.

    Research 4.6 records why this replaced the lag-1 autocorrelation the
    specification first named: at the 0.05 T spacing of the reference data
    adjacent residuals are correlated whatever the model does, and every fit
    scores close to the maximum on autocorrelation. The runs test is
    insensitive to the sampling density, and scores the same residual strongly
    negative.

    Returns `-inf` when every residual shares one sign, which is as
    structured as a residual can be, and NaN when there are too few points to
    say anything.
    """
    r = np.asarray(residual, dtype=float)
    signs = np.sign(r)
    signs = signs[signs != 0.0]
    n = signs.size
    if n < 2:
        return float("nan")

    n_positive = int(np.count_nonzero(signs > 0))
    n_negative = n - n_positive
    if n_positive == 0 or n_negative == 0:
        return float("-inf")

    runs = 1 + int(np.count_nonzero(signs[1:] != signs[:-1]))
    expected = 2.0 * n_positive * n_negative / n + 1.0
    variance = (
        2.0
        * n_positive
        * n_negative
        * (2.0 * n_positive * n_negative - n)
        / (n**2 * (n - 1.0))
    )
    if variance <= 0.0:
        return float("nan")
    return (runs - expected) / float(np.sqrt(variance))


def condition_number(jacobian) -> float:
    """Ratio of largest to smallest singular value. FR-055, AC-010.

    The argument is the derivative of the residual vector with respect to the
    fitted parameters at the solution. Because the search runs in the
    logarithm of the parameters and the residuals are normalised, the ratio is
    dimensionless and comparable between runs.

    Research 4.6 calibrates it against four cases whose parameter accuracy is
    known: the reference data set, whose value is in that record and is not
    published with the program; `4.0e2` for a synthetic fit good to 0.1 %,
    `5.2e3` for one wrong by 35 %, and `3.6e9` for two same-sign carriers
    given nearly equal mobilities. Returns `inf` where the
    smallest singular value is zero.
    """
    singular = singular_values(jacobian)
    if singular.size == 0:
        return float("nan")
    if singular[-1] == 0.0:
        return float("inf")
    return float(singular[0] / singular[-1])


def singular_values(jacobian):
    """Singular values of the residual derivative, largest first."""
    j = np.asarray(jacobian, dtype=float)
    if j.ndim != 2:
        raise ValueError(f"jacobian must be two-dimensional, got shape {j.shape}")
    return np.linalg.svd(j, compute_uv=False)
