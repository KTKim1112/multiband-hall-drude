"""The search: parameters in log space, bounds, multistart, one temperature.

`plan.md` section 3 fixes the parameter vector as
`[log n_0, log mu_0, log n_1, log mu_1, ...]`, in the boundary units of
NR-004. Log space is NR-002: a step is then a fractional change, densities
spanning six decades and mobilities five become commensurate, positivity
(NR-001) is automatic rather than enforced, and the search is invariant to
the units the parameters were declared in.

It also holds the three temperature strategies of FR-023 to FR-026. They
differ only in what is added to the objective and where the search starts;
the objective at one temperature is the same in all three.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .config import CarrierSpec, ResolvedConfig
from .core import penalties as penalty_module
from .core import residual as residual_module
from .core.canonical import canonicalise, join_parameters, split_parameters
from .core.drude import resistivity
from .core.errors import MbfitError
from .core.metrics import condition_number, r_squared, rmse, singular_values


#: How often the coupled fit of a band reports, in residual evaluations. A
#: least-squares run has no known total, so elapsed against the budget is the
#: only honest denominator; this only decides how often it is refreshed.
_GLOBAL_REPORT_EVERY = 25


class FitStopped(Exception):
    """The caller asked for the fit to stop. Nothing is wrong; nothing is kept.

    Raised from inside the residual, for the same reason the budget is checked
    there: one call of `least_squares` over a band of thirteen sweeps ran
    3061 s (research 005 section 6), so a check between starts would leave a
    stop request unanswered for the better part of an hour.
    """


class _BudgetExpired(Exception):
    """One start ran past the wall clock of FR-088. Caught, never raised out.

    A private exception rather than a flag because it has to unwind out of
    `least_squares`, which offers no other way to stop it mid-iteration.
    """
from .core.units import density_to_si, mobility_to_si, resistivity_to_si
from .dataio import Dataset, TemperatureGroup

# How close to a log bound counts as sitting on it, for NR-006.
_BOUND_SNAP = 1e-12


# ------------------------------------------------------------- per temperature

def _matching_key(mapping: dict[str, Any], T_K: float) -> str | None:
    """Find the entry for a temperature, comparing as numbers not as text.

    `5`, `5.0` and `5.00` name the same temperature, and a document should not
    have to guess which spelling the reader used.
    """
    for key in mapping:
        try:
            if float(key) == float(T_K):
                return key
        except (TypeError, ValueError):
            continue
    return None


def effective_carriers(config: ResolvedConfig, T_K: float):
    """Carrier specifications for one temperature. FR-016 and FR-054.

    Returns `(specs, overrides)`, where `overrides` records every value that
    a per-temperature section replaced, with the default beside it. FR-054
    requires that record, because a bound that varies with temperature is the
    one setting in this program capable of drawing a trajectory by hand.
    """
    specs: list[CarrierSpec] = []
    overrides: list[dict[str, Any]] = []

    initial_key = _matching_key(config.initial_by_temperature, T_K)
    initial = config.initial_by_temperature.get(initial_key, {}) if initial_key else {}
    override_key = _matching_key(config.overrides_by_temperature, T_K)
    replacement = config.overrides_by_temperature.get(override_key, {}) if override_key else {}

    for carrier in config.carriers:
        values = {
            "density": {
                "init": carrier.n_init_cm3,
                "min": carrier.n_min_cm3,
                "max": carrier.n_max_cm3,
            },
            "mobility": {
                "init": carrier.mu_init_cm2Vs,
                "min": carrier.mu_min_cm2Vs,
                "max": carrier.mu_max_cm2Vs,
            },
        }

        for quantity, declared in initial.get(carrier.name, {}).items():
            values[quantity]["init"] = float(declared)
            overrides.append(
                {
                    "T_K": float(T_K),
                    "carrier": carrier.name,
                    "quantity": quantity,
                    "field": "init",
                    "default": getattr(
                        carrier, "n_init_cm3" if quantity == "density" else "mu_init_cm2Vs"
                    ),
                    "override": float(declared),
                    "source": "initial_by_temperature",
                }
            )

        for quantity, declared in replacement.get(carrier.name, {}).items():
            for bound_name, bound_value in declared.items():
                default = values[quantity][bound_name]
                values[quantity][bound_name] = float(bound_value)
                overrides.append(
                    {
                        "T_K": float(T_K),
                        "carrier": carrier.name,
                        "quantity": quantity,
                        "field": bound_name,
                        "default": default,
                        "override": float(bound_value),
                        "source": "overrides_by_temperature",
                    }
                )

        density = values["density"]
        mobility = values["mobility"]
        for quantity, bounds in (("density", density), ("mobility", mobility)):
            if bounds["min"] <= 0.0 or bounds["min"] > bounds["max"]:
                raise MbfitError(
                    "E_CONFIG_BOUNDS_INVALID",
                    T_K=float(T_K),
                    carrier=carrier.name,
                    quantity=quantity,
                    min=bounds["min"],
                    max=bounds["max"],
                )
            if not (bounds["min"] <= bounds["init"] <= bounds["max"]):
                raise MbfitError(
                    "E_CONFIG_INIT_OUT_OF_BOUNDS",
                    T_K=float(T_K),
                    carrier=carrier.name,
                    quantity=quantity,
                    init=bounds["init"],
                    min=bounds["min"],
                    max=bounds["max"],
                )

        specs.append(
            CarrierSpec(
                name=carrier.name,
                kind=carrier.kind,
                n_init_cm3=density["init"],
                n_min_cm3=density["min"],
                n_max_cm3=density["max"],
                mu_init_cm2Vs=mobility["init"],
                mu_min_cm2Vs=mobility["min"],
                mu_max_cm2Vs=mobility["max"],
                smooth_density=carrier.smooth_density,
                smooth_mobility=carrier.smooth_mobility,
                monotonic_density=carrier.monotonic_density,
                monotonic_mobility=carrier.monotonic_mobility,
            )
        )
    return specs, overrides


# --------------------------------------------------------- the parameter vector

def initial_vector(specs) -> np.ndarray:
    """Declared initial values, in boundary units, flat."""
    return join_parameters(
        [s.n_init_cm3 for s in specs], [s.mu_init_cm2Vs for s in specs]
    )


def bounds(specs):
    """`(low, high)` in boundary units, flat."""
    low = join_parameters([s.n_min_cm3 for s in specs], [s.mu_min_cm2Vs for s in specs])
    high = join_parameters([s.n_max_cm3 for s in specs], [s.mu_max_cm2Vs for s in specs])
    return low, high


def signs(specs) -> np.ndarray:
    return np.asarray([s.sign for s in specs], dtype=float)


def encode(params) -> np.ndarray:
    """Boundary units to the log vector the search moves in. NR-002."""
    p = np.asarray(params, dtype=float)
    if np.any(p <= 0.0):
        raise ValueError("NR-001 violated: every parameter must be positive to be encoded")
    return np.log(p)


def decode(x, low=None, high=None) -> np.ndarray:
    """The log vector back to boundary units, with NR-006 applied.

    A component the search left sitting on a bound is reported as the declared
    bound itself, not as the exponential of its logarithm, which differs in
    the last bit and would make a result look interior when it is not.
    """
    p = np.exp(np.asarray(x, dtype=float))
    if low is None or high is None:
        return p
    low = np.asarray(low, dtype=float)
    high = np.asarray(high, dtype=float)
    x = np.asarray(x, dtype=float)
    p = np.where(x <= np.log(low) + _BOUND_SNAP, low, p)
    p = np.where(x >= np.log(high) - _BOUND_SNAP, high, p)
    return p


def at_bound(params, low, high, fraction: float):
    """Which parameters rest within `fraction` of a bound. FR-043, AC-003.

    Read literally: within 0.5 % of the bound *value*, so `p <= min (1 + f)`
    or `p >= max (1 - f)`. The alternative, a fraction of the log-space span
    between the bounds, would depend on how wide the other bound was set.
    """
    p = np.asarray(params, dtype=float)
    low = np.asarray(low, dtype=float)
    high = np.asarray(high, dtype=float)
    return (p <= low * (1.0 + fraction)), (p >= high * (1.0 - fraction))


# ------------------------------------------------------------------- the model

def model_resistivity(B_T, params, sign, hall_polarity: float = 1.0):
    """Model `rho_xx`, `rho_xy` in boundary units, from boundary-unit params."""
    n_cm3, mu_cm2Vs = split_parameters(params)
    rho_xx_si, rho_xy_si = resistivity(
        B_T, density_to_si(n_cm3), mobility_to_si(mu_cm2Vs), sign, hall_polarity
    )
    from .core.units import resistivity_from_si

    return resistivity_from_si(rho_xx_si), resistivity_from_si(rho_xy_si)


# ---------------------------------------------------------------- the results

@dataclass(frozen=True)
class StartResult:
    """One starting point and where it landed. `data-model.md` section 1.4."""

    start_index: int
    params: np.ndarray
    cost: float
    converged: bool


@dataclass(frozen=True)
class TemperatureFit:
    """The answer at one temperature. `data-model.md` section 1.5."""

    T_K: float
    params: np.ndarray
    params_canonical: np.ndarray
    starts: tuple[StartResult, ...]
    channel_scales: tuple[float, float]
    seed: int
    r2_rhoxx: float
    r2_rhoxy: float
    rmse_rhoxx: float
    rmse_rhoxy: float
    r2_outside: float | None
    rmse_outside: float | None
    singular_values: np.ndarray
    condition_number: float
    at_bound_low: np.ndarray
    at_bound_high: np.ndarray
    overrides: tuple[dict[str, Any], ...] = ()
    specs: tuple[CarrierSpec, ...] = field(default_factory=tuple)


# ------------------------------------------------------------ the objective

def make_objective(group: TemperatureGroup, config: ResolvedConfig, sign):
    """The residual of one temperature, as a function of the log vector.

    Returned with the channel scales it fixed, because FR-020 computes them
    from the measurement once and they have to be recorded with the result.
    Every strategy uses this, so the objective at one temperature is the same
    whether it is fitted alone, seeded from below, or as part of a global
    problem. Only what is added to it differs.
    """
    optimisation = config.optimization
    polarity = float(config.model["hall_polarity"])
    B = group.B_T
    measured_xx_si = resistivity_to_si(group.rhoxx_uohmcm)
    measured_xy_si = resistivity_to_si(group.rhoxy_uohmcm)
    mask = group.in_fit_window

    scales = residual_module.channel_scales(
        measured_xx_si[mask], measured_xy_si[mask], optimisation["fit_space"], polarity
    )

    def objective(x):
        params = decode(x)
        model_xx, model_xy = resistivity(
            B,
            density_to_si(params[0::2]),
            mobility_to_si(params[1::2]),
            sign,
            polarity,
        )
        return residual_module.residual_vector(
            B,
            measured_xx_si,
            measured_xy_si,
            model_xx,
            model_xy,
            fit_mode=optimisation["fit_mode"],
            fit_space=optimisation["fit_space"],
            hall_polarity=polarity,
            weight_rhoxx=optimisation["weight_rhoxx"],
            weight_rhoxy=optimisation["weight_rhoxy"],
            low_field_enabled=optimisation["low_field_weight"]["enabled"],
            low_field_alpha=optimisation["low_field_weight"]["alpha"],
            low_field_B0_T=optimisation["low_field_weight"]["B0_T"],
            scales=scales,
            mask=mask,
        )

    return objective, scales


def log_jacobian(objective, x, step: float = 1e-6):
    """Derivative of the residual with respect to the log parameters. FR-055.

    Computed here rather than taken from the solver, so that the conditioning
    means the same thing under every strategy: under the global one the
    solver returns the Jacobian of the whole coupled problem, which is a
    different matrix and a different question.
    """
    x = np.asarray(x, dtype=float)
    base = np.asarray(objective(x), dtype=float)
    columns = np.empty((base.size, x.size), dtype=float)
    for index in range(x.size):
        shifted = x.copy()
        shifted[index] += step
        columns[:, index] = (np.asarray(objective(shifted), dtype=float) - base) / step
    return columns


# ------------------------------------------------------------------ the search

def _temperature_seed(base_seed: int, T_K: float) -> int:
    """A seed derived from the run seed and the temperature itself.

    Keyed on the temperature rather than its position, so that adding a
    temperature to a series does not change the starting points chosen for
    any other. NR-005 and Article VII.
    """
    return int(abs(int(base_seed)) * 1_000_003 + abs(int(round(float(T_K) * 1e6)))) % (2**63)


def fit_temperature(
    group: TemperatureGroup,
    config: ResolvedConfig,
    start_from=None,
) -> TemperatureFit:
    """Fit one temperature from several starting points. FR-033 to FR-036.

    `start_from` replaces the declared initial value for start 0, which is how
    the sequential strategy of Phase 4 will seed a temperature from the one
    below it. Nothing else about the objective changes.
    """
    specs, overrides = effective_carriers(config, group.T_K)
    low, high = bounds(specs)
    sign = signs(specs)
    optimisation = config.optimization
    polarity = float(config.model["hall_polarity"])

    B = group.B_T
    mask = group.in_fit_window
    objective, scales = make_objective(group, config, sign)

    # FR-088 and NR-012. The budget has to be checked inside the residual: a
    # single `least_squares` call ran for 2082 s during the search of research
    # 004 section 2, so a check between starts would not have bounded it. The
    # start that expires is abandoned and the others continue, which is what
    # makes the budget a bound on one fit rather than on the whole run.
    budget = float(optimisation.get("fit_budget_s", 0.0) or 0.0)
    expired: list[int] = []
    # One deadline for the whole fit, not one per start. FR-088 bounds a fit,
    # and research 004 section 2 measured fits: a per-start clock let a
    # degenerate combination run twelve starts of thirty seconds each.
    fit_deadline = time.monotonic() + budget if budget > 0.0 else None

    log_low, log_high = np.log(low), np.log(high)
    declared_start = initial_vector(specs) if start_from is None else np.asarray(start_from, float)
    x0 = np.clip(encode(declared_start), log_low, log_high)

    seed = _temperature_seed(optimisation["random_seed"], group.T_K)
    generator = np.random.default_rng(seed)
    sigma = float(optimisation["multi_start_log_sigma"])

    starts: list[StartResult] = []
    best = None
    for index in range(int(optimisation["multi_start"])):
        if index == 0:
            start = x0
        else:
            start = np.clip(x0 + generator.normal(0.0, sigma, x0.shape), log_low, log_high)
        if fit_deadline is not None and time.monotonic() > fit_deadline:
            expired.append(index)
            continue
        guarded = objective
        if fit_deadline is not None:

            def guarded(vector, _inner=objective, _stop=fit_deadline):
                if time.monotonic() > _stop:
                    raise _BudgetExpired()
                return _inner(vector)

        try:
            outcome = least_squares(
                guarded,
                start,
                bounds=(log_low, log_high),
                loss=optimisation["loss"],
                f_scale=optimisation["f_scale"],
                max_nfev=int(optimisation["max_nfev"]),
                ftol=optimisation["ftol"],
                xtol=optimisation["xtol"],
                gtol=optimisation["gtol"],
            )
        except _BudgetExpired:
            expired.append(index)
            continue
        except (ValueError, FloatingPointError):
            continue
        starts.append(
            StartResult(
                start_index=index,
                params=decode(outcome.x, low, high),
                cost=float(outcome.cost),
                converged=bool(outcome.success),
            )
        )
        if best is None or outcome.cost < best.cost:
            best = outcome

    if best is None:
        raise MbfitError(
            "E_FIT_NO_START",
            T_K=float(group.T_K),
            n_attempted=int(optimisation["multi_start"]),
        )

    params = decode(best.x, low, high)
    jacobian = log_jacobian(objective, best.x)
    model_xx, model_xy = model_resistivity(B, params, sign, polarity)

    inside = mask
    outside = ~mask
    below_low, above_high = at_bound(params, low, high, config.acceptance["bound_fraction"])

    return TemperatureFit(
        T_K=float(group.T_K),
        params=params,
        params_canonical=canonicalise(params, sign),
        starts=tuple(starts),
        channel_scales=(float(scales[0]), float(scales[1])),
        seed=seed,
        r2_rhoxx=r_squared(group.rhoxx_uohmcm[inside], model_xx[inside]),
        r2_rhoxy=r_squared(group.rhoxy_uohmcm[inside], model_xy[inside]),
        rmse_rhoxx=rmse(group.rhoxx_uohmcm[inside], model_xx[inside]),
        rmse_rhoxy=rmse(group.rhoxy_uohmcm[inside], model_xy[inside]),
        r2_outside=(
            r_squared(group.rhoxx_uohmcm[outside], model_xx[outside])
            if np.any(outside)
            else None
        ),
        rmse_outside=(
            rmse(group.rhoxx_uohmcm[outside], model_xx[outside]) if np.any(outside) else None
        ),
        singular_values=singular_values(jacobian),
        condition_number=condition_number(jacobian),
        at_bound_low=below_low,
        at_bound_high=above_high,
        overrides=tuple(overrides),
        specs=tuple(specs),
    )


# ---------------------------------------------------------- the whole series

@dataclass(frozen=True)
class RunResult:
    """Everything one run produced. `data-model.md` section 1.7."""

    config: ResolvedConfig
    fits: tuple[TemperatureFit, ...]
    strategy: str
    seed: int
    order_changes: tuple[int, ...] = ()
    global_condition_number: float | None = None

    @property
    def temperatures(self) -> tuple[float, ...]:
        return tuple(fit.T_K for fit in self.fits)


def stacked_log_parameters(fits) -> np.ndarray:
    return np.vstack([encode(fit.params) for fit in fits])


def fit_independent(dataset: Dataset, config: ResolvedConfig, *,
                    progress=None, stop=None):
    """FR-023. Each temperature with no reference to any other.

    The baseline every later result is compared against, and the honest place
    to start: whatever the parameters do here, the data asked for it.

    The stop is checked between temperatures, which is what FR-098 asks of a
    strategy that fits them one at a time. Without it a stop went unanswered
    until every remaining sweep had been fitted -- minutes, on a table of
    twelve (AC-033).
    """
    fits = []
    for index, group in enumerate(dataset.groups):
        if stop is not None and stop():
            raise FitStopped()
        if progress is not None:
            progress(index, len(dataset.groups))
        fits.append(fit_temperature(group, config))
    return fits


def fit_sequential(dataset: Dataset, config: ResolvedConfig, *,
                   progress=None, stop=None):
    """FR-024. The result at one temperature seeds the next, and nothing else.

    No penalty couples the temperatures. This changes where the search starts,
    not what is minimised, and the two are kept apart so that a Methods
    section can say which of them was in force.

    The stop is checked between temperatures, as in `fit_independent`.
    """
    fits = []
    previous = None
    for index, group in enumerate(dataset.groups):
        if stop is not None and stop():
            raise FitStopped()
        if progress is not None:
            progress(index, len(dataset.groups))
        fit = fit_temperature(group, config, start_from=previous)
        fits.append(fit)
        previous = fit.params
    return fits


def global_residual(flat, groups, objectives, config, sign, temperatures, n_parameters):
    """Every temperature, plus what couples them. FR-025."""
    X = flat.reshape(len(groups), n_parameters)
    parts = [objective(X[index]) for index, objective in enumerate(objectives)]

    smoothing = config.smoothing
    if smoothing["enabled"]:
        parts.append(
            penalty_module.coupling_residual(
                X,
                temperatures,
                sign,
                order=int(smoothing["order"]),
                lambda_density=smoothing["lambda_density"],
                lambda_mobility=smoothing["lambda_mobility"],
                smooth_density=[c.smooth_density for c in config.carriers],
                smooth_mobility=[c.smooth_mobility for c in config.carriers],
                breaks=smoothing["breaks_K"],
            )
        )
    monotonic = config.monotonic_penalty
    if monotonic["enabled"]:
        parts.append(
            penalty_module.monotonic_residual(
                X,
                temperatures,
                sign,
                strength=monotonic["lambda"],
                density_directions=[c.monotonic_density for c in config.carriers],
                mobility_directions=[c.monotonic_mobility for c in config.carriers],
                breaks=smoothing["breaks_K"],
            )
        )
    return np.concatenate([part for part in parts if part.size])


def fit_global(dataset: Dataset, config: ResolvedConfig, *,
               progress=None, stop=None):
    """FR-025. Every temperature as one problem, so that a coupling can act.

    This is the only strategy in which the penalties of specification section
    5.7 exist at all.
    """
    groups = dataset.groups
    temperatures = np.asarray([group.T_K for group in groups], dtype=float)
    optimisation = config.optimization

    per_temperature = [effective_carriers(config, group.T_K) for group in groups]
    specs_by_group = [entry[0] for entry in per_temperature]
    overrides_by_group = [entry[1] for entry in per_temperature]
    sign = signs(specs_by_group[0])
    n_parameters = 2 * len(config.carriers)

    objectives, scales_by_group = [], []
    for group in groups:
        objective, scales = make_objective(group, config, sign)
        objectives.append(objective)
        scales_by_group.append(scales)

    low_by_group = [bounds(specs) for specs in specs_by_group]
    low = np.concatenate([np.log(pair[0]) for pair in low_by_group])
    high = np.concatenate([np.log(pair[1]) for pair in low_by_group])
    x0 = np.concatenate(
        [
            np.clip(encode(initial_vector(specs)), np.log(pair[0]), np.log(pair[1]))
            for specs, pair in zip(specs_by_group, low_by_group)
        ]
    )

    def residual(flat):
        return global_residual(
            flat, groups, objectives, config, sign, temperatures, n_parameters
        )

    # AC-039. Its own budget, checked inside the residual. A band is a
    # different size of problem from a sweep -- thirteen sweeps are 104
    # parameters against eight -- so `fit_budget_s` of thirty seconds would
    # expire every start of every band worth coupling. And the check has to be
    # here rather than between starts: one call ran 3061 s (research 005
    # section 6), so a check between starts bounds nothing.
    budget = float(optimisation.get("global_budget_s", 0.0) or 0.0)
    deadline = time.monotonic() + budget if budget > 0.0 else None
    started = time.monotonic()
    evaluations = 0
    watching = deadline is not None or stop is not None or progress is not None

    def watched(flat):
        nonlocal evaluations
        evaluations += 1
        if deadline is not None and time.monotonic() > deadline:
            raise _BudgetExpired()
        if stop is not None and stop():
            raise FitStopped()
        if progress is not None and evaluations % _GLOBAL_REPORT_EVERY == 0:
            progress(evaluations=evaluations,
                     seconds=round(time.monotonic() - started, 1),
                     budget=round(budget, 1) if budget > 0.0 else None)
        return residual(flat)

    seed = _temperature_seed(optimisation["random_seed"], float(np.sum(temperatures)))
    generator = np.random.default_rng(seed)
    sigma = float(optimisation["multi_start_log_sigma"])

    best = None
    expired = 0
    all_starts: list[list[StartResult]] = [[] for _ in groups]
    for index in range(int(optimisation["multi_start"])):
        start = (
            x0
            if index == 0
            else np.clip(x0 + generator.normal(0.0, sigma, x0.shape), low, high)
        )
        if progress is not None:
            progress(start=index, starts=int(optimisation["multi_start"]),
                     seconds=round(time.monotonic() - started, 1),
                     budget=round(budget, 1) if budget > 0.0 else None)
        if stop is not None and stop():
            raise FitStopped()
        try:
            outcome = least_squares(
                watched if watching else residual,
                start,
                bounds=(low, high),
                loss=optimisation["loss"],
                f_scale=optimisation["f_scale"],
                max_nfev=int(optimisation["max_nfev"]),
                ftol=optimisation["ftol"],
                xtol=optimisation["xtol"],
                gtol=optimisation["gtol"],
            )
        except _BudgetExpired:
            expired += 1
            continue
        except (ValueError, FloatingPointError):
            continue
        landed = outcome.x.reshape(len(groups), n_parameters)
        for group_index, pair in enumerate(low_by_group):
            all_starts[group_index].append(
                StartResult(
                    start_index=index,
                    params=decode(landed[group_index], pair[0], pair[1]),
                    cost=float(outcome.cost),
                    converged=bool(outcome.success),
                )
            )
        if best is None or outcome.cost < best.cost:
            best = outcome

    if best is None:
        # Say which it was. A band abandoned by the clock is a band that needs
        # dividing or a longer budget; a band no start could fit is a different
        # problem, and a reader told the wrong one looks in the wrong place.
        raise MbfitError("E_FIT_NO_START",
                         n_attempted=int(optimisation["multi_start"]),
                         n_expired=expired)

    X = best.x.reshape(len(groups), n_parameters)
    polarity = float(config.model["hall_polarity"])
    fits = []
    for index, group in enumerate(groups):
        group_low, group_high = low_by_group[index]
        params = decode(X[index], group_low, group_high)
        jacobian = log_jacobian(objectives[index], X[index])
        model_xx, model_xy = model_resistivity(group.B_T, params, sign, polarity)
        inside = group.in_fit_window
        outside = ~inside
        below, above = at_bound(
            params, group_low, group_high, config.acceptance["bound_fraction"]
        )
        fits.append(
            TemperatureFit(
                T_K=group.T_K,
                params=params,
                params_canonical=canonicalise(params, sign),
                starts=tuple(all_starts[index]),
                channel_scales=(
                    float(scales_by_group[index][0]),
                    float(scales_by_group[index][1]),
                ),
                seed=seed,
                r2_rhoxx=r_squared(group.rhoxx_uohmcm[inside], model_xx[inside]),
                r2_rhoxy=r_squared(group.rhoxy_uohmcm[inside], model_xy[inside]),
                rmse_rhoxx=rmse(group.rhoxx_uohmcm[inside], model_xx[inside]),
                rmse_rhoxy=rmse(group.rhoxy_uohmcm[inside], model_xy[inside]),
                r2_outside=(
                    r_squared(group.rhoxx_uohmcm[outside], model_xx[outside])
                    if np.any(outside)
                    else None
                ),
                rmse_outside=(
                    rmse(group.rhoxx_uohmcm[outside], model_xx[outside])
                    if np.any(outside)
                    else None
                ),
                singular_values=singular_values(jacobian),
                condition_number=condition_number(jacobian),
                at_bound_low=below,
                at_bound_high=above,
                overrides=tuple(overrides_by_group[index]),
                specs=tuple(specs_by_group[index]),
            )
        )
    return fits, seed, condition_number(best.jac)


STRATEGIES = {
    "independent": fit_independent,
    "sequential": fit_sequential,
    "global_smooth": fit_global,
}


def fit_dataset(dataset: Dataset, config: ResolvedConfig, *,
                progress=None, stop=None) -> RunResult:
    """Fit every temperature by the declared strategy, and record which. FR-026.

    `progress` and `stop` are plain callables, as in `uncertainty`, and reach
    every strategy. The coupled one solves the whole band in a single call and
    could not otherwise be seen or ended at all; the other two are checked
    between temperatures, because a stop that waits for twelve sweeps to
    finish is not a stop (FR-098, AC-033).
    """
    from .config import validate_against_temperatures

    validate_against_temperatures(config, dataset.temperatures)
    strategy = config.optimization["temperature_strategy"]

    global_condition = None
    if strategy == "global_smooth":
        fits, seed, global_condition = fit_global(
            dataset, config, progress=progress, stop=stop)
    else:
        fits = STRATEGIES[strategy](dataset, config, progress=progress, stop=stop)
        seed = fits[0].seed if fits else int(config.optimization["random_seed"])

    sign = signs(fits[0].specs) if fits else np.zeros(0)
    changes = (
        tuple(penalty_module.order_changes(stacked_log_parameters(fits), sign))
        if len(fits) > 1
        else ()
    )
    return RunResult(
        config=config,
        fits=tuple(fits),
        strategy=strategy,
        seed=seed,
        order_changes=changes,
        global_condition_number=global_condition,
    )
