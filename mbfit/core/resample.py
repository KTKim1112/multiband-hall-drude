"""Circular block resampling of a field-ordered residual. FR-059.

An independent resample of a residual assumes the residual is independent.
Research 002 section 3.2 measured what that assumption costs here: a real
sample's residuals score strongly negative on the runs test, and an
independent resample of them understates the parameter uncertainty severalfold.
Moving contiguous blocks preserves correlation up to the block length, and the
measured interval then reaches the independent estimate of research 001
section 4.8 at a block length of about 20.

The blocks are circular: the sequence is treated as a loop so that every
record has the same chance of appearing, and no block runs off the end and has
to be discarded or shortened. The cost of that choice is that a block
spanning the wrap joins the high-field end to the low-field one, which is not
a sequence the measurement could produce. What it produces instead is a
perturbation of the right size and the right correlation length, which is what
the resample is for.

Note what a block length equal to the record count does: it draws a random
rotation of the residual, not the residual itself. Research 002 section 3.2
records the measurement.
"""

from __future__ import annotations

import numpy as np


def block_indices(n_records: int, block_length: int, generator) -> np.ndarray:
    """Indices of one circular block resample of `n_records` records.

    Drawn as `ceil(n / L)` blocks of length `L` from uniformly random starts,
    concatenated and truncated to `n`. Truncating the last block rather than
    padding keeps the output the same length as the input, which is what lets
    the caller add it to a model curve without deciding what to do with a
    ragged tail.
    """
    n = int(n_records)
    L = int(block_length)
    if n <= 0:
        raise ValueError("n_records must be positive")
    if L <= 0:
        raise ValueError("block_length must be positive")
    L = min(L, n)

    starts = generator.integers(0, n, size=(n + L - 1) // L)
    offsets = np.arange(L)
    indices = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)
    return indices[:n]


def block_resample(values, block_length: int, generator) -> np.ndarray:
    """One circular block resample of `values`."""
    y = np.asarray(values, dtype=float)
    if y.ndim != 1:
        raise ValueError("values must be one-dimensional")
    return y[block_indices(y.size, block_length, generator)]


def interval(samples, fraction: float):
    """The central `fraction` of a sample, as `(low, high)`.

    A percentile interval rather than a multiple of the standard deviation,
    because the resampled parameter distributions here are not symmetric: the
    parameters are fitted in the logarithm, so a symmetric excursion in
    `log n` is an asymmetric one in `n`, and reporting `value +/- sigma` would
    quietly place part of the interval where the search could never go.
    """
    x = np.asarray(samples, dtype=float)
    if x.size == 0:
        raise ValueError("samples must not be empty")
    f = float(fraction)
    if not 0.0 < f < 1.0:
        raise ValueError("fraction must lie strictly between 0 and 1")
    tail = 0.5 * (1.0 - f)
    low, high = np.quantile(x, [tail, 1.0 - tail])
    return float(low), float(high)


def correlation(samples) -> np.ndarray:
    """Correlation matrix of resampled parameters, columns as parameters.

    Taken on the relative excursion rather than the raw value, so that a
    density of `1e21` and a mobility of `1e3` contribute comparably. A column
    that never moved gets a zero row and column rather than a division by
    zero: it is uncorrelated with everything because it carries no variation
    to correlate.
    """
    X = np.asarray(samples, dtype=float)
    if X.ndim != 2:
        raise ValueError("samples must be two-dimensional")
    centre = X.mean(axis=0)
    spread = X.std(axis=0)
    alive = spread > 0.0

    C = np.zeros((X.shape[1], X.shape[1]), dtype=float)
    if not np.any(alive):
        return C
    Z = (X[:, alive] - centre[alive]) / spread[alive]
    live = (Z.T @ Z) / X.shape[0]
    C[np.ix_(alive, alive)] = np.clip(live, -1.0, 1.0)
    np.fill_diagonal(C, np.where(alive, 1.0, 0.0))
    return C
