"""The mobility spectrum, by separating the carrier types first.

FR-067 to FR-076. Five steps, and the third is the one that matters:

    1  normalise      X = sigma_xx/sigma_xx(0),  Y = sigma_xy/sigma_xx(0)
    2  extend         fit n Lorentzians to X and Y sharing one mobility set
    3  transform      X', Y' by the closed forms of `core/lorentzian.py`
    4  separate       X^p, X^n, Y^p, Y^n by the identities of `core/separation.py`
    5  invert         one positive spectrum per carrier type, then read peaks

Step 2 exists only to serve step 3: the transform is an integral over all
fields, so `X` and `Y` have to be defined outside the measured range. It is
not a physical model and its order carries no physical meaning, which is a
claim this project measures rather than repeats -- see the gate on the order
in `tests/test_spectrum.py`.

An earlier version of this module skipped steps 2 to 4 and inverted the
unseparated data on a signed grid. It could not decide how many carriers there
were: the count moved between six and two with the regularisation. The reason
is that hole and electron contributions partially cancel in `Y`, so many
different splits fit equally well. Separating first removes that freedom
entirely, and research 003 section 3 records the same machinery then returning
one answer over eleven decades of regularisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import least_squares, nnls

from .config import ResolvedConfig
from .core import lorentzian, separation
from .core import spectrum as core
from .core.constants import ELEMENTARY_CHARGE_C
from .core.drude import (
    SIGN_ELECTRON,
    SIGN_HOLE,
    conductivity_from_resistivity,
    resistivity as drude_resistivity,
)
from .core.units import (
    density_from_si,
    density_to_si,
    mobility_from_si,
    mobility_to_si,
    resistivity_from_si,
    resistivity_to_si,
)
from .dataio import Dataset, TemperatureGroup
from .fitting import RunResult, model_resistivity, signs

NNLS_MAX_ITERATIONS = 20000

HOLE = "hole"
ELECTRON = "electron"


@dataclass(frozen=True)
class Step:
    """One regularisation strength and what it gave, for one carrier type."""

    kind: str
    alpha: float
    residual_norm: float
    roughness: float
    n_peaks: int


@dataclass(frozen=True)
class Extension:
    """The Lorentzian extension of step 2, and how well it described the data."""

    n_terms: int
    amplitude_X: np.ndarray          # a_j
    amplitude_Y: np.ndarray          # b_j
    weight_hole: np.ndarray          # p_j, the hole conductivity of term j
    weight_electron: np.ndarray      # q_j, the electron conductivity of term j
    mobility_m2Vs: np.ndarray
    cost: float
    max_relative_residual: float
    n_starts: int
    n_starts_agreeing: int
    constrained: bool
    at_bound: bool


@dataclass(frozen=True)
class Branch:
    """The spectrum of one carrier type."""

    kind: str
    mu_grid_m2Vs: np.ndarray
    density: np.ndarray
    peaks: tuple[dict[str, Any], ...]
    alpha: float
    steps: tuple[Step, ...]
    plateaus: tuple[tuple[int, int], ...]
    noise_reached: bool
    negative_fraction: float


@dataclass(frozen=True)
class TemperatureSpectrum:
    """Everything step 1 to 5 learned about one sweep."""

    T_K: float
    sigma_xx_zero: float
    zero_field_records: int
    extension: Extension
    branches: tuple[Branch, ...]
    noise: tuple[float, float]
    noise_source: str
    target_residual_norm: float
    recombination_error: float
    roundtrip_rhoxx: float
    roundtrip_rhoxy: float
    roundtrip_tolerance: float

    def branch(self, kind: str) -> Branch:
        for entry in self.branches:
            if entry.kind == kind:
                return entry
        raise KeyError(kind)

    @property
    def proposal(self) -> dict[str, int]:
        """How many carriers of each sign the spectrum suggests. FR-075.

        A suggestion. FR-076 keeps the decision with the reader: this number
        is reported beside how stable it was, and the carrier count that is
        actually fitted stays the one the configuration declares.
        """
        return {entry.kind: len(entry.peaks) for entry in self.branches}

    @property
    def ambiguous(self) -> bool:
        """Any carrier type whose count is not settled across the range."""
        return any(len(entry.plateaus) > 1 for entry in self.branches)

    @property
    def unresolved(self) -> bool:
        return any(len(entry.plateaus) == 0 for entry in self.branches)

    @property
    def roundtrip(self) -> float:
        """The worse of the two channels. FR-079."""
        return max(self.roundtrip_rhoxx, self.roundtrip_rhoxy)


# --------------------------------------------------------------- step 1 and 2

def noise_from_residual(y) -> float:
    """High-frequency content of a residual, via second differences."""
    d2 = np.diff(np.asarray(y, dtype=float), n=2)
    if d2.size == 0:
        return 0.0
    mad = float(np.median(np.abs(d2 - np.median(d2))))
    return mad / 0.6744897501960817 / np.sqrt(6.0)


def _weights_at(B_T, X, Y, mu_m2Vs):
    """The best non-negative `(p, q)` for a fixed set of mobilities.

    A linear problem, so it is solved rather than guessed. Rows are scaled by
    each channel's own size first: `Y` is an order of magnitude smaller than
    `X` here, and an unscaled least squares would fit the longitudinal channel
    and ignore the Hall one, which is the channel carrying the carrier sign.
    """
    design = lorentzian.design(B_T, mu_m2Vs)
    n_records = np.asarray(B_T).size
    scale_X = max(float(np.max(np.abs(X))), np.finfo(float).tiny)
    scale_Y = max(float(np.max(np.abs(Y))), np.finfo(float).tiny)
    row = np.concatenate([np.full(n_records, scale_X), np.full(n_records, scale_Y)])
    data = np.concatenate([np.asarray(X, dtype=float), np.asarray(Y, dtype=float)])
    weights, _ = nnls(design / row[:, None], data / row, maxiter=NNLS_MAX_ITERATIONS)
    n = np.asarray(mu_m2Vs).size
    return weights[:n], weights[n:]


def fit_extension(B_T, X, Y, n_terms, mu_min, mu_max, n_starts, seed,
                  constrained: bool = True, start_pqmu=None) -> Extension:
    """Step 2. `n` Lorentzians to both channels at once. FR-068, NR-011.

    Both channels in one residual, because the transform of step 3 is exact
    only when `X` and `Y` share their mobilities. Multistart because this is a
    nonlinear fit with its own local minima: measured during design, the exact
    global minimum of a six-term noiseless problem was reached from roughly one
    start in ten.

    `constrained` is the important argument. In the constrained variables of
    `core/lorentzian.py`, `p_j >= 0` and `q_j >= 0` make the separated
    conductivities non-negative by construction, and the extension becomes a
    `2n`-carrier Drude model rather than an arbitrary curve. Turning it off
    reproduces the published method exactly, and research 003 section 6 records
    what that costs: a basin in which two terms take large cancelling weights,
    indistinguishable in fit quality from a good solution, that sends a
    separated conductivity to `-77.7` where its true range is `+0.02` to
    `+0.50` -- and which basin the search finds depends on how many starts it
    was given. So the default is on, and off is recorded as a prior.
    """
    B = np.asarray(B_T, dtype=float)
    generator = np.random.default_rng(seed)
    n = int(n_terms)

    if constrained:
        function, splitter = lorentzian.residual_constrained, lorentzian.split_weights
        low = np.concatenate([np.zeros(n), np.zeros(n), np.full(n, np.log(mu_min))])
    else:
        function, splitter = lorentzian.residual, lorentzian.split
        low = np.concatenate([
            np.zeros(n), np.full(n, -np.inf), np.full(n, np.log(mu_min))
        ])
    high = np.concatenate([
        np.full(n, np.inf), np.full(n, np.inf), np.full(n, np.log(mu_max))
    ])

    best = None
    costs = []
    for index in range(int(n_starts)):
        if index == 0 and start_pqmu is not None and constrained:
            # FR-080, spectrum mode. The outer loop hands back the carriers of
            # the previous fit as a starting point, one carrier per term. It
            # only makes sense in the constrained variables, where a term is a
            # hole weight and an electron weight.
            p0, q0, mu0 = start_pqmu
            start = lorentzian.join_weights(
                p0, q0, np.clip(np.asarray(mu0, dtype=float), mu_min, mu_max))
            try:
                found = least_squares(
                    function, np.clip(start, low, high), bounds=(low, high),
                    args=(n, B, X, Y), max_nfev=40000,
                )
            except (ValueError, np.linalg.LinAlgError):
                continue
            costs.append(float(found.cost))
            if best is None or found.cost < best.cost:
                best = found
            continue
        if index == 0:
            mu0 = np.geomspace(mu_min, mu_max, n)
        else:
            mu0 = np.exp(np.sort(generator.uniform(np.log(mu_min), np.log(mu_max), n)))

        # Given the mobilities, the weights are a *linear* non-negative
        # problem, so there is no reason to guess them: solve for them. This
        # is variable projection used only to start, which costs one small
        # NNLS per start and measurably shortens the search -- the nonlinear
        # part then only has to move the mobilities.
        first, second = _weights_at(B, X, Y, mu0)
        if not constrained:
            second = mu0 * (first - second)          # back to b_j
            first = first + second / np.where(mu0 > 0, mu0, 1.0)
            first, second = lorentzian.ab_from_weights(*_weights_at(B, X, Y, mu0), mu0)
        start = np.concatenate([first, second, np.log(mu0)])
        try:
            found = least_squares(
                function, np.clip(start, low, high), bounds=(low, high),
                args=(n, B, X, Y), max_nfev=40000,
            )
        except (ValueError, np.linalg.LinAlgError):
            continue
        costs.append(float(found.cost))
        if best is None or found.cost < best.cost:
            best = found
    if best is None:
        raise RuntimeError("no Lorentzian start converged")

    if constrained:
        p, q, mu = lorentzian.split_weights(best.x, n)
        a, b = lorentzian.ab_from_weights(p, q, mu)
    else:
        a, b, mu = lorentzian.split(best.x, n)
        p, q = lorentzian.weights_from_ab(a, b, mu)

    model_X, model_Y = lorentzian.evaluate(B, a, b, mu)
    worst = max(
        float(np.max(np.abs(model_X - X)) / max(np.max(np.abs(X)), 1e-300)),
        float(np.max(np.abs(model_Y - Y)) / max(np.max(np.abs(Y)), 1e-300)),
    )
    floor = min(costs) if costs else float("inf")
    agreeing = sum(1 for c in costs if c <= floor * 1.01)

    order = np.argsort(-mu)
    return Extension(
        n_terms=n,
        amplitude_X=a[order],
        amplitude_Y=b[order],
        weight_hole=p[order],
        weight_electron=q[order],
        mobility_m2Vs=mu[order],
        cost=float(best.cost),
        max_relative_residual=worst,
        n_starts=int(n_starts),
        n_starts_agreeing=int(agreeing),
        constrained=bool(constrained),
        at_bound=bool(
            np.any(mu <= mu_min * (1 + 1e-9)) or np.any(mu >= mu_max * (1 - 1e-9))
        ),
    )


# ------------------------------------------------------------------- step 5

def solve_at(B_T, part_X, part_Y, mu_grid, alpha, weight):
    """One inversion of one carrier type. NR-010: the density stays positive."""
    A, b, K, d, w, L = core.augmented(B_T, mu_grid, alpha, part_X, part_Y, weight)
    s, _ = nnls(A, b, maxiter=NNLS_MAX_ITERATIONS)
    return s, core.residual_norm(K, s, d, w), core.roughness(L, s)


def strengths(settings) -> np.ndarray:
    low = float(settings["alpha_min"])
    high = float(settings["alpha_max"])
    if not (0.0 < low <= high):
        raise ValueError("need 0 < alpha_min <= alpha_max")
    count = max(2, int(round(np.log10(high / low))) + 1)
    return np.logspace(np.log10(low), np.log10(high), count)


def invert_branch(kind, B_T, part_X, part_Y, mu_grid, weight, settings, target) -> Branch:
    """The spectrum of one carrier type, over the whole regularisation range."""
    steps: list[Step] = []
    selected = None
    for alpha in strengths(settings):
        s, residual, rough = solve_at(B_T, part_X, part_Y, mu_grid, alpha, weight)
        found = core.peaks(mu_grid, s, float(settings["peak_floor"]),
                           float(settings["peak_floor"]))
        steps.append(
            Step(kind=kind, alpha=float(alpha), residual_norm=residual,
                 roughness=rough, n_peaks=len(found))
        )
        if residual <= target:
            selected = (float(alpha), s, found)

    reached = selected is not None
    if not reached:
        alpha = float(steps[0].alpha)
        s, _, _ = solve_at(B_T, part_X, part_Y, mu_grid, alpha, weight)
        selected = (alpha, s, core.peaks(mu_grid, s, float(settings["peak_floor"]),
                                         float(settings["peak_floor"])))

    alpha, density, found = selected
    return Branch(
        kind=kind,
        mu_grid_m2Vs=mu_grid,
        density=density,
        peaks=tuple(found),
        alpha=alpha,
        steps=tuple(steps),
        plateaus=tuple(core.plateaus([step.n_peaks for step in steps],
                                     int(settings["plateau_decades"]))),
        noise_reached=reached,
        negative_fraction=max(
            separation.negative_fraction(part_X),
            separation.negative_fraction(part_Y, B_T),
        ),
    )


def carriers_from(branch: Branch, sigma_xx_zero: float):
    """Peaks as carriers, in boundary units. FR-074.

    The weight of a peak is the fraction of the zero-field conductivity that
    peak carries, because the spectrum solves the *normalised* problem and
    `X(0) = 1`. So

        sigma_xx(0) * S_i = n_i q mu_i

    and the density follows. This is the step that turns a picture into
    numbers a fit can be started from.
    """
    out = []
    for entry in branch.peaks:
        mu_si = float(entry["mu_m2Vs"])
        weight = float(entry["weight"])
        n_si = sigma_xx_zero * weight / (ELEMENTARY_CHARGE_C * mu_si)
        out.append({
            "kind": branch.kind,
            "mobility_cm2Vs": mobility_from_si(mu_si),
            "density_cm3": density_from_si(n_si),
            "weight": weight,
        })
    return sorted(out, key=lambda item: -item["mobility_cm2Vs"])


def round_trip(group: TemperatureGroup, branches, sigma_xx_zero: float,
               hall_polarity: float) -> tuple[float, float]:
    """Put the peaks back through PM-001 and compare with the measurement.

    FR-079. Every step before this one is judged against something internal --
    how well the extension fitted, whether a plateau formed, whether the parts
    recombined. None of that asks the only question a reader actually has,
    which is whether the carriers the spectrum ends up reporting describe the
    sweep they came from.

    It is worth its own number because the internal checks can all pass while
    this fails. Research 003 section 8 measures a synthetic sweep at `0.2 %`
    noise and a real one whose extension residuals agree to within a fifth --
    `4.9e-2` against `5.2e-2` -- and whose round trips are `3.7 %` and `26.8 %`.
    What separates them is not how large the extension residual is but whether
    it has structure, and this is the measurement that sees the difference.

    Reported per channel because the failure is lopsided: the density of
    FR-074 is fixed by `sigma_xx(0)` alone, so the Hall channel is the one
    carrying no constraint and the one that goes wrong first.
    """
    carriers = [
        item for branch in branches
        for item in carriers_from(branch, sigma_xx_zero)
    ]
    if not carriers:
        return float("nan"), float("nan")

    n_si = density_to_si(np.array([c["density_cm3"] for c in carriers], dtype=float))
    mu_si = mobility_to_si(np.array([c["mobility_cm2Vs"] for c in carriers], dtype=float))
    sign = np.array(
        [SIGN_HOLE if c["kind"] == HOLE else SIGN_ELECTRON for c in carriers], dtype=float
    )
    model_xx, model_xy = drude_resistivity(group.B_T, n_si, mu_si, sign, hall_polarity)
    model_xx = resistivity_from_si(model_xx)
    model_xy = resistivity_from_si(model_xy)

    def relative(model, measured):
        scale = float(np.max(np.abs(measured)))
        if scale <= 0.0:
            return float("nan")
        return float(np.max(np.abs(model - measured)) / scale)

    return (relative(model_xx, group.rhoxx_uohmcm),
            relative(model_xy, group.rhoxy_uohmcm))


# ---------------------------------------------------------------- the driver

def for_temperature(fit, group: TemperatureGroup, config: ResolvedConfig,
                    seed=None) -> TemperatureSpectrum:
    settings = config.spectrum
    polarity = float(config.model["hall_polarity"])

    sigma_xx, sigma_xy = conductivity_from_resistivity(
        resistivity_to_si(group.rhoxx_uohmcm),
        resistivity_to_si(group.rhoxy_uohmcm),
        polarity,
    )
    sigma0, n_zero = lorentzian.zero_field_value(
        group.B_T, sigma_xx, float(settings["zero_field_window_T"])
    )
    if sigma0 <= 0.0:
        raise ValueError("sigma_xx(0) must be positive")
    X, Y = sigma_xx / sigma0, sigma_xy / sigma0

    extension = fit_extension(
        group.B_T, X, Y,
        int(settings["lorentzian_terms"]),
        mobility_to_si(float(settings["mu_min_cm2Vs"])),
        mobility_to_si(float(settings["mu_max_cm2Vs"])),
        int(settings["lorentzian_multi_start"]),
        int(config.optimization["random_seed"]),
        bool(settings["lorentzian_constrained"]),
        seed,
    )

    X_transformed, Y_transformed = lorentzian.transform(
        group.B_T, extension.amplitude_X, extension.amplitude_Y, extension.mobility_m2Vs
    )
    Xp, Xn, Yp, Yn = separation.separate(X, Y, X_transformed, Y_transformed)
    back_X, back_Y = separation.recombine(Xp, Xn, Yp, Yn)
    recombination = max(
        float(np.max(np.abs(back_X - X)) / max(np.max(np.abs(X)), 1e-300)),
        float(np.max(np.abs(back_Y - Y)) / max(np.max(np.abs(Y)), 1e-300)),
    )

    source = settings["noise_source"]
    if source == "residual":
        model_xx, model_xy = model_resistivity(
            group.B_T, fit.params, signs(fit.specs), polarity
        )
        fitted_xx, fitted_xy = conductivity_from_resistivity(
            resistivity_to_si(model_xx), resistivity_to_si(model_xy), polarity
        )
        noise = (
            noise_from_residual((sigma_xx - fitted_xx) / sigma0),
            noise_from_residual((sigma_xy - fitted_xy) / sigma0),
        )
    else:
        noise = (float(source[0]), float(source[1]))
    if not all(value > 0.0 for value in noise):
        raise ValueError("the noise level must be positive in both channels")

    mu_grid = core.positive_grid(
        mobility_to_si(float(settings["mu_min_cm2Vs"])),
        mobility_to_si(float(settings["mu_max_cm2Vs"])),
        int(settings["points_per_decade"]),
    )
    weight = np.concatenate([
        np.full(group.B_T.size, noise[0]),
        np.full(group.B_T.size, noise[1]),
    ])
    target = float(settings["discrepancy_factor"]) * core.expected_residual_norm(group.B_T.size)

    branches = (
        invert_branch(HOLE, group.B_T, Xp, Yp, mu_grid, weight, settings, target),
        invert_branch(ELECTRON, group.B_T, Xn, Yn, mu_grid, weight, settings, target),
    )

    rt_xx, rt_xy = round_trip(group, branches, sigma0, polarity)

    return TemperatureSpectrum(
        T_K=fit.T_K,
        sigma_xx_zero=sigma0,
        zero_field_records=n_zero,
        extension=extension,
        branches=branches,
        noise=noise,
        noise_source=str(settings["noise_source"]),
        target_residual_norm=target,
        recombination_error=recombination,
        roundtrip_rhoxx=rt_xx,
        roundtrip_rhoxy=rt_xy,
        roundtrip_tolerance=float(settings["roundtrip_tolerance"]),
    )


def estimate(result: RunResult, dataset: Dataset):
    """Every temperature, or nothing when the feature is switched off."""
    if not result.config.spectrum["enabled"]:
        return ()
    return tuple(
        for_temperature(fit, group, result.config)
        for fit, group in zip(result.fits, dataset.groups)
    )
