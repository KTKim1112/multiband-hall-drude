"""Is this carrier set one non-circular orbit wearing multiband clothes?

Research 002 section 4. A single non-circular orbit, solved by Chambers with
the velocity expanded in cyclotron harmonics, gives

    sigma  ~  sum_m  w_m / [1 + (m mu B)^2]

which is the multiband Drude form with effective mobilities `mu, mu/2, mu/3,
...`. One band and one scattering time can therefore be fitted as several
carriers, and the fit will be good.

The signature has three parts and all three must hold at once:

    ratios      the mobilities stand in ratios of consecutive small integers
    weights     their weights fall monotonically along the ladder
    sign        every channel carries the same sign

The sign condition is the sharpest of the three, because the harmonics of one
orbit cannot change the sign of the charge carrying it. A mixed-sign set is
not a ladder whatever its ratios do, which is why `verdict` reports the three
separately rather than as one number: a reader who sees a near-integer ratio
set should be able to see that it failed on the sign alone.
"""

from __future__ import annotations

import numpy as np

MAX_HARMONIC = 12


def ladder_ratios(mobility):
    """Each mobility as a ratio to the largest, in descending mobility order."""
    mu = np.asarray(mobility, dtype=float)
    if mu.ndim != 1 or mu.size == 0:
        raise ValueError("mobility must be a non-empty one-dimensional array")
    if np.any(mu <= 0.0):
        raise ValueError("mobility must be positive")
    order = np.argsort(-mu)
    return order, mu[order[0]] / mu[order]


def nearest_harmonic(ratios, tolerance: float):
    """For each ratio, the harmonic index it matches, or 0 for none.

    Index `m` means the channel looks like the `m`-th harmonic, whose
    effective mobility is `mu / m`. A ratio beyond `MAX_HARMONIC` is reported
    as no match rather than as a very high harmonic: the weights of a real
    expansion fall away long before that, so a match there would be an
    accident of arithmetic.
    """
    r = np.asarray(ratios, dtype=float)
    index = np.rint(r).astype(int)
    matched = (
        (index >= 1)
        & (index <= MAX_HARMONIC)
        & (np.abs(r - index) <= float(tolerance) * index)
    )
    return np.where(matched, index, 0)


def verdict(density, mobility, sign, tolerance: float):
    """The three conditions of research 002 section 4, reported separately.

    `density` stands in for the weight of each channel: in the expansion the
    weight is what multiplies each harmonic, and here it is the carrier
    density that does. Returns a mapping, never a single boolean, because
    which condition failed is the information a reader needs.
    """
    n = np.asarray(density, dtype=float)
    mu = np.asarray(mobility, dtype=float)
    s = np.asarray(sign, dtype=float)
    if not (n.shape == mu.shape == s.shape):
        raise ValueError("density, mobility and sign must have the same shape")

    order, ratios = ladder_ratios(mu)
    harmonics = nearest_harmonic(ratios, tolerance)
    weights = n[order]

    single_sign = bool(np.all(s == s[0]))
    consecutive = bool(
        np.all(harmonics > 0)
        and harmonics[0] == 1
        and np.array_equal(np.sort(harmonics), np.arange(1, harmonics.size + 1))
    )
    falling = bool(np.all(np.diff(weights) <= 0.0))

    return {
        "order": order,
        "ratios": ratios,
        "harmonics": harmonics,
        "weights": weights,
        "single_sign": single_sign,
        "consecutive_integers": consecutive,
        "falling_weights": falling,
        "is_ladder": bool(single_sign and consecutive and falling),
        "failed": tuple(
            name
            for name, held in (
                ("single_sign", single_sign),
                ("consecutive_integers", consecutive),
                ("falling_weights", falling),
            )
            if not held
        ),
    }
