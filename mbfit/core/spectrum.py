"""The mobility spectrum, in the parts that need no solver.

FR-072 and FR-073. After `separation.py` has split the measurement into a
hole part and an electron part, each part is a **positive** linear inverse
problem on its own:

    X^k(B) = sum_j  s^k_j / [1 + mu_j^2 B^2]
    Y^k(B) = sum_j  s^k_j mu_j B / [1 + mu_j^2 B^2]      k = hole or electron

with `s^k_j >= 0` the conductivity density and `mu_j > 0` throughout. Both
signs use the *same* kernel, which is the reason `separation.py` returns
amplitudes rather than signed parts.

An earlier version of this module put both carrier types on one signed grid
and solved once. Research 003 section 3 records what that cost: the peak count
moved between six and two across the regularisation range, because the two
carrier types partially cancel in the unseparated data and the inversion could
not tell which of several splits the measurement meant. The same machinery,
applied after separation, returns the same count over eleven decades.

Article I keeps the core to one array library and the standard library, and a
non-negative least-squares solver is neither, so what lives here is the
geometry -- the grid, the kernel, the penalty, and reading peaks off a
solution -- while `mbfit/spectrum.py` does the solving.
"""

from __future__ import annotations

import numpy as np


def positive_grid(mu_min_m2Vs: float, mu_max_m2Vs: float, points_per_decade: int):
    """Log-spaced mobilities, ascending, all positive.

    Log-spaced and not linear because a second difference along the array is
    then a second difference in `ln mu`, which is the variable the published
    method discretises and the one in which a carrier occupies a fixed width
    whatever its mobility. A linear grid would resolve a fast carrier and
    smear a slow one with the same penalty.

    One grid serves both carrier types: the sign lives in which separated part
    is being inverted, not in the grid.
    """
    if not (0.0 < mu_min_m2Vs < mu_max_m2Vs):
        raise ValueError("need 0 < mu_min < mu_max")
    if points_per_decade < 1:
        raise ValueError("points_per_decade must be at least 1")
    decades = np.log10(mu_max_m2Vs / mu_min_m2Vs)
    count = max(3, int(round(decades * points_per_decade)))
    return np.logspace(np.log10(mu_min_m2Vs), np.log10(mu_max_m2Vs), count)


def kernel(B_T, mu_grid_m2Vs):
    """Rows: the longitudinal block then the Hall block. Columns: the grid.

    Applied to one separated carrier type at a time, so every entry of the
    Hall block is positive and the two blocks reinforce rather than cancel.
    """
    B = np.atleast_1d(np.asarray(B_T, dtype=float))[:, None]
    mu = np.atleast_1d(np.asarray(mu_grid_m2Vs, dtype=float))[None, :]
    denominator = 1.0 + (mu * B) ** 2
    return np.vstack([1.0 / denominator, mu * B / denominator])


def second_difference(n: int) -> np.ndarray:
    """The smoothing operator: what the penalty measures the roughness of."""
    if n < 3:
        return np.zeros((0, max(n, 0)), dtype=float)
    rows = np.zeros((n - 2, n), dtype=float)
    for index in range(n - 2):
        rows[index, index] = 1.0
        rows[index, index + 1] = -2.0
        rows[index, index + 2] = 1.0
    return rows


def augmented(B_T, mu_grid, alpha: float, sigma_xx, sigma_xy, weight):
    """The system a non-negative solver is handed, and its right-hand side.

    Rows are divided by their own noise, so the residual norm of a fit that
    explains the data to the noise is about the square root of the row count.
    That is what makes the discrepancy principle of FR-069 a fixed target
    rather than a quantity to be calibrated per data set.
    """
    K = kernel(B_T, mu_grid)
    d = np.concatenate([
        np.atleast_1d(np.asarray(sigma_xx, dtype=float)),
        np.atleast_1d(np.asarray(sigma_xy, dtype=float)),
    ])
    w = np.atleast_1d(np.asarray(weight, dtype=float))
    if w.shape != d.shape:
        raise ValueError(f"weight {w.shape} does not match the data {d.shape}")
    if np.any(w <= 0.0):
        raise ValueError("weights must be positive")
    if float(alpha) < 0.0:
        raise ValueError("alpha must not be negative")

    L = second_difference(np.asarray(mu_grid).size)
    A = np.vstack([K / w[:, None], np.sqrt(float(alpha)) * L])
    b = np.concatenate([d / w, np.zeros(L.shape[0])])
    return A, b, K, d, w, L


def residual_norm(K, s, d, w) -> float:
    return float(np.linalg.norm((K @ s - d) / w))


def roughness(L, s) -> float:
    return float(np.linalg.norm(L @ s)) if L.shape[0] else 0.0


def expected_residual_norm(n_records: int) -> float:
    """What a fit at the noise level scores, once the rows are weighted."""
    return float(np.sqrt(2 * int(n_records)))


def peaks(mu_grid, s, floor_fraction: float, weight_floor: float = 0.0):
    """Local maxima of the density, each with a mobility and a weight.

    A peak's mobility is the centre of mass over the contiguous region where
    the density stays above half that peak, rather than the grid point of the
    maximum: the grid is discrete and the maximum lands on whichever point is
    nearest, which quantises the answer to the grid spacing for no reason.

    Two maxima sharing a half-height region are one peak. Without that rule a
    slightly ragged top counts twice, and the peak count is the number this
    feature exists to report.

    `weight_floor` is an **absolute** threshold and it is not optional in
    practice. `floor_fraction` compares a maximum with the largest in the same
    branch, which says nothing when the whole branch is empty: measured on an
    all-hole synthetic system, the electron branch came back at exactly zero
    conductivity and the peak finder still reported a peak in it, at
    `118571 cm^2/Vs` carrying `0.000 %` of the spectrum. The normalisation of
    FR-067 makes the absolute test easy -- the two branches together sum to
    `X(0) = 1` -- so a peak carrying less than `weight_floor` of that is not a
    carrier and is dropped.

    **The weight is taken over a different region from the centre, and the
    difference matters.** The centre wants a narrow region, because the tails
    of a smoothed peak are where a neighbour bleeds in and they would drag the
    mobility. The weight wants the whole peak, because `weight` becomes a
    carrier density through FR-074 and anything left outside is density thrown
    away. Measured during design: taking the weight over the half-height
    region alone biased recovered densities low by 14 to 24 % on synthetic data
    whose answer was known. So the weights partition the grid at the valleys
    between peaks, and therefore sum to the whole spectrum.
    """
    mu = np.asarray(mu_grid, dtype=float)
    density = np.asarray(s, dtype=float)
    if mu.shape != density.shape:
        raise ValueError("grid and density must have the same shape")
    if np.any(mu <= 0.0):
        raise ValueError("the grid must be positive; separate the signs first")
    if density.size < 3 or density.max() <= 0.0:
        return []

    threshold = float(floor_fraction) * float(density.max())
    candidates = []
    for index in range(1, density.size - 1):
        if not (density[index] > threshold
                and density[index] >= density[index - 1]
                and density[index] > density[index + 1]):
            continue
        half = 0.5 * density[index]
        low = index
        while low > 0 and density[low - 1] > half:
            low -= 1
        high = index
        while high < density.size - 1 and density[high + 1] > half:
            high += 1
        core_weight = float(np.sum(density[low:high + 1]))
        centre = float(np.sum(density[low:high + 1] * mu[low:high + 1]) / core_weight)
        candidates.append({
            "mu_m2Vs": centre,
            "height": float(density[index]),
            "index": index,
            "span": (low, high),
        })

    kept: list[dict] = []
    for entry in sorted(candidates, key=lambda item: -item["height"]):
        if any(entry["span"] == other["span"] for other in kept):
            continue
        kept.append(entry)
    kept.sort(key=lambda item: item["mu_m2Vs"])
    if not kept:
        return []

    # Partition the grid at the valleys between adjacent maxima, so that every
    # grid point belongs to exactly one peak and the weights sum to the whole
    # spectrum. Nothing is discarded: a density this inversion put somewhere is
    # a conductivity the measurement contains.
    edges = [0]
    for left, right in zip(kept[:-1], kept[1:]):
        lo, hi = left["index"], right["index"]
        edges.append(lo + 1 + int(np.argmin(density[lo + 1:hi + 1])))
    edges.append(density.size)

    for entry, start, stop in zip(kept, edges[:-1], edges[1:]):
        entry["weight"] = float(np.sum(density[start:stop]))
        entry["weight_span"] = (int(start), int(stop))

    floor = float(weight_floor)
    if floor > 0.0:
        kept = [entry for entry in kept if entry["weight"] >= floor]
    return kept


def plateaus(counts, minimum_run: int):
    """Runs of consecutive strengths returning the same count. FR-073, AC-020.

    Returned as `(count, length)` pairs, longest first. A single plateau is an
    answer; more than one is the ambiguity of FR-073, under which no peak
    count should be quoted at all, and none is a count the range never settled.
    """
    values = list(int(c) for c in counts)
    if not values:
        return []
    runs: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or values[index] != values[start]:
            runs.append((values[start], index - start))
            start = index
    kept = [run for run in runs if run[1] >= int(minimum_run)]
    return sorted(kept, key=lambda run: (-run[1], -run[0]))
