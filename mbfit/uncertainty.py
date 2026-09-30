"""Parameter intervals by resampling the residual. FR-058 to FR-062.

What this covers, and what it does not, is the whole of the design.

It covers the part of the uncertainty that resampling the residual can reach:
if the same measurement were repeated and the residual fell differently, this
is how far the carriers would move. Research 002 section 3.2 measured that on
this sample against the independent estimate of research 001 section 4.8, and
they agree at a block length of about 20.

It does not cover the misspecification that made the residual structured in
the first place. A converged fit leaves a residual orthogonal to the Jacobian,
so the residual it carries cannot move it at all, and no resampling of that
residual recovers what a *different* residual of the same size would have
done. That is why FR-060 pairs the interval with the runs test: where FR-046
fires, the interval is a lower bound, and the amount by which it understates
is the amount by which the residual is structured.

The parameters are resampled in canonical order. PM-003 makes the declared
order meaningless, and two resamples that differ only by a relabelling would
otherwise contribute a spurious spread and a spurious correlation.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import ResolvedConfig
from .core import resample as resample_module
from .core.canonical import canonicalise
from .dataio import Dataset, TemperatureGroup
from .fitting import (
    RunResult,
    TemperatureFit,
    _temperature_seed as fitting_temperature_seed,
    fit_temperature,
    model_resistivity,
    signs,
)

class Stopped(Exception):
    """A caller asked the resampling to stop. FR-101.

    Nothing partial is kept: an interval from a fraction of the draws is a
    different interval, not an early look at the same one.
    """


# Derived quantities of FR-061, in the order they are reported.
DERIVED = ("hole_density", "electron_density", "hole_over_electron", "hole_minus_electron")


@dataclass(frozen=True)
class Interval:
    """One quantity, its value, and the central fraction of its resamples."""

    name: str
    value: float
    low: float
    high: float
    sigma: float

    def as_row(self) -> dict[str, Any]:
        return {
            "quantity": self.name,
            "value": self.value,
            "low": self.low,
            "high": self.high,
            "one_sigma": self.sigma,
            "relative_one_sigma": self.sigma / abs(self.value) if self.value else float("nan"),
        }


@dataclass(frozen=True)
class TemperatureUncertainty:
    """Everything the resampling learned at one temperature."""

    T_K: float
    names: tuple[str, ...]
    samples: np.ndarray                 # (resamples, 2N), canonical order
    parameters: tuple[Interval, ...]
    derived: tuple[Interval, ...]
    correlation: np.ndarray
    block_length: int
    resamples: int
    seed: int
    lower_bound: bool                   # FR-060


def parameter_names(fit: TemperatureFit) -> tuple[str, ...]:
    """Canonical position names: kind and rank, never the declared name.

    The canonical order moves carriers within a sign group, so the kind at a
    position is fixed while the declared name at it is not. Naming a column
    after a declared carrier would attach a name to a quantity that is not
    always that carrier.
    """
    names: list[str] = []
    for index, spec in enumerate(fit.specs):
        names.append(f"canonical{index + 1}_{spec.kind}_density")
        names.append(f"canonical{index + 1}_{spec.kind}_mobility")
    return tuple(names)


def derived_quantities(params_canonical, sign) -> dict[str, float]:
    """FR-061. The combinations, which are not among the parameters.

    Research 002 section 3.4 measured why this is not decoration: the totals
    are four times better determined than the individual carriers and their
    difference six times worse, so eight parameters with eight intervals hide
    the two numbers a reader will actually quote.
    """
    n = np.asarray(params_canonical, dtype=float)[0::2]
    s = np.asarray(sign, dtype=float)
    holes = float(np.sum(n[s > 0]))
    electrons = float(np.sum(n[s < 0]))
    return {
        "hole_density": holes,
        "electron_density": electrons,
        "hole_over_electron": holes / electrons if electrons else float("nan"),
        "hole_minus_electron": holes - electrons,
    }


def _temperature_seed(base: int, T_K: float) -> int:
    """Distinct per temperature and reproducible, keyed on the temperature.

    Offset from the run seed so that a resampling draw never repeats the
    multistart draw of the same temperature, and derived the same way as
    NR-005 does it, so that adding a temperature to a series leaves every
    other temperature's stream alone. `hash` would not do: it is not stable
    across interpreters, and FR-037 promises the run reproduces.
    """
    return fitting_temperature_seed(int(base) + 7_919, T_K)


def resample_temperature(
    fit: TemperatureFit,
    group: TemperatureGroup,
    config: ResolvedConfig,
    structured: bool = False,
    progress=None,
    stop=None,
) -> TemperatureUncertainty:
    """Refit `resamples` rebuilt sweeps and collect what moved. FR-058.

    `progress(done, total)` is called after each draw and `stop()` is asked
    before it, so a caller can show the work and end it (FR-101). Neither
    changes a draw: the generator advances exactly as it does without them.
    """
    settings = config.uncertainty
    draws = int(settings["resamples"])
    block = int(settings["block_length"])
    fraction = float(settings["interval_fraction"])
    base = settings["seed"]
    if base is None:
        base = int(config.optimization["random_seed"])
    seed = _temperature_seed(base, fit.T_K)
    generator = np.random.default_rng(seed)

    sign = signs(fit.specs)
    polarity = float(config.model["hall_polarity"])
    model_xx, model_xy = model_resistivity(group.B_T, fit.params, sign, polarity)
    residual_xx = group.rhoxx_uohmcm - model_xx
    residual_xy = group.rhoxy_uohmcm - model_xy

    # NR-008: no parity is enforced on the resample. The Jacobian of a
    # symmetric sweep carries the parity of its channel, so the wrong-parity
    # half of any perturbation changes the cost and not the answer. Research
    # 002 section 3.1 measured it.
    collected = np.empty((draws, fit.params.size), dtype=float)
    for index in range(draws):
        if stop is not None and stop():
            raise Stopped()
        rebuilt = dataclasses.replace(
            group,
            rhoxx_uohmcm=model_xx + resample_module.block_resample(residual_xx, block, generator),
            rhoxy_uohmcm=model_xy + resample_module.block_resample(residual_xy, block, generator),
        )
        refit = fit_temperature(rebuilt, config, start_from=fit.params)
        collected[index] = canonicalise(refit.params, sign)
        if progress is not None:
            progress(index + 1, draws)

    names = parameter_names(fit)
    parameters = tuple(
        Interval(
            name=name,
            value=float(fit.params_canonical[column]),
            low=resample_module.interval(collected[:, column], fraction)[0],
            high=resample_module.interval(collected[:, column], fraction)[1],
            sigma=float(np.std(collected[:, column])),
        )
        for column, name in enumerate(names)
    )

    truth = derived_quantities(fit.params_canonical, sign)
    drawn = {key: [] for key in DERIVED}
    for row in collected:
        for key, value in derived_quantities(row, sign).items():
            drawn[key].append(value)
    derived = tuple(
        Interval(
            name=key,
            value=truth[key],
            low=resample_module.interval(np.asarray(drawn[key]), fraction)[0],
            high=resample_module.interval(np.asarray(drawn[key]), fraction)[1],
            sigma=float(np.std(drawn[key])),
        )
        for key in DERIVED
    )

    return TemperatureUncertainty(
        T_K=fit.T_K,
        names=names,
        samples=collected,
        parameters=parameters,
        derived=derived,
        correlation=resample_module.correlation(collected),
        block_length=block,
        resamples=draws,
        seed=seed,
        lower_bound=bool(structured),
    )


def structured_temperatures(result: RunResult, dataset: Dataset) -> set[float]:
    """Temperatures whose residual trips FR-046, for FR-060.

    Computed here rather than taken from the diagnostics list, so that the
    uncertainty module does not have to be run after the diagnostics or to
    know their shape. The threshold is the same AC-007 either way.
    """
    from .core.metrics import runs_test_z

    threshold = float(result.config.acceptance["residual_runs_z"])
    polarity = float(result.config.model["hall_polarity"])
    structured: set[float] = set()
    for fit, group in zip(result.fits, dataset.groups):
        mask = group.in_fit_window
        model_xx, model_xy = model_resistivity(group.B_T, fit.params, signs(fit.specs), polarity)
        for measured, modelled in (
            (group.rhoxx_uohmcm, model_xx),
            (group.rhoxy_uohmcm, model_xy),
        ):
            score = runs_test_z((measured - modelled)[mask])
            if np.isfinite(score) and score < threshold:
                structured.add(fit.T_K)
    return structured


def estimate(result: RunResult, dataset: Dataset):
    """Every temperature, or nothing when the feature is switched off."""
    if not result.config.uncertainty["enabled"]:
        return ()
    structured = structured_temperatures(result, dataset)
    return tuple(
        resample_temperature(fit, group, result.config, fit.T_K in structured)
        for fit, group in zip(result.fits, dataset.groups)
    )
