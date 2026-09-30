"""The configuration document: schema, defaults, validation, resolution.

This is `data-model.md` section 2 in code. Two rules shape it.

Unknown fields are rejected rather than ignored, so that a typo in an option
name cannot silently leave a default in force. A misspelled `lambda_denisty`
must not quietly mean "no density coupling".

Every default is inert. A document declaring only `columns` and `carriers`
gets the unconstrained diagnostic fit of stage A: no coupling between
temperatures, no monotonic expectation, no low-field emphasis, no field
window, ordinary least squares, each temperature fitted on its own. That is
the honest starting point, and turning any of it on brings Article X with it.
"""

from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass, field
from typing import Any

from .core.drude import sign_of_kind
from .core.errors import MbfitError

SCHEMA_VERSION = "1.0"

FIT_MODES = ("both", "rhoxx", "rhoxy")
FIT_SPACES = ("rho", "sigma")
STRATEGIES = ("independent", "sequential", "global_smooth")
LOSSES = ("linear", "soft_l1", "huber", "cauchy", "arctan")
MONOTONIC = ("none", "increase", "decrease")
CARRIER_KINDS = ("electron", "hole")

# Every optional section, with the value used when the document is silent.
# The shape of this mapping is also the schema: a key absent from here is an
# unknown field.
DEFAULTS: dict[str, Any] = {
    "model": {
        "hall_polarity": 1.0,
    },
    "preprocess": {
        "rhoxy_scale": 1.0,
        "symmetrize_rhoxx": False,
        "antisymmetrize_rhoxy": False,
        "mirror_interpolate": True,
        "mirror_tolerance_T": 1e-9,
    },
    "optimization": {
        "fit_mode": "both",
        "fit_space": "rho",
        "weight_rhoxx": 1.0,
        "weight_rhoxy": 1.0,
        "low_field_weight": {"enabled": False, "alpha": 5.0, "B0_T": 1.0},
        "fit_field_range": {"enabled": False, "abs_min_T": 0.0, "abs_max_T": None},
        "temperature_strategy": "independent",
        "multi_start": 8,
        "multi_start_log_sigma": 0.25,
        "random_seed": 12345,
        "loss": "linear",
        "f_scale": 1.0,
        "max_nfev": 30000,
        # AC-029 and FR-088. A wall clock for one fit, in seconds; 0 removes
        # it. Research 004 section 2 measured 8 fits of 83 taking 88 % of a
        # search and every one of them failing the selection anyway, so the
        # budget costs nothing and saves 84 % of the time.
        "fit_budget_s": 30.0,
        # AC-039. One coupled fit over a whole band, which is a different
        # size of problem from one sweep: measured at 3061 s for thirteen
        # sweeps (research 005 section 6). Reusing the 30 s above would
        # expire every start of every band of more than five temperatures.
        "global_budget_s": 1800.0,
        "ftol": 1e-12,
        "xtol": 1e-12,
        "gtol": 1e-12,
    },
    "smoothing": {
        "enabled": False,
        "order": 2,
        "lambda_density": 0.0,
        "lambda_mobility": 0.0,
        "breaks_K": [],
    },
    "monotonic_penalty": {
        "enabled": False,
        "lambda": 10.0,
    },
    "acceptance": {
        "r2_rhoxx_min": 0.995,
        "r2_rhoxy_min": 0.995,
        "bound_fraction": 0.005,
        "jump_factor": 5.0,
        "cost_equivalence": 0.01,
        "parameter_difference": 0.20,
        "residual_runs_z": -3.0,
        "excluded_rms_ratio": 3.0,
        "condition_number_max": 1000.0,
    },
    # Feature 002. `uncertainty` is opt-in because a resampling run costs
    # `resamples` fits per temperature; `discriminants` holds only thresholds,
    # which decide what is reported and never what is fitted, so they are
    # inert in the sense of feature 001 and always on.
    "uncertainty": {
        "enabled": False,
        "resamples": 200,
        "block_length": 20,
        "interval_fraction": 0.68,
        "seed": None,
    },
    "discriminants": {
        "harmonic_tolerance": 0.05,
        "parity_threshold": 0.02,
    },
    # Feature 003. Opt-in like `uncertainty`: one constrained inversion per
    # regularisation step. `noise_source` is the setting a reader has to think
    # about -- research 003 section 5 measured the peak count moving from six
    # to two between two defensible answers for it on the same sweep.
    "spectrum": {
        "enabled": False,
        "mu_min_cm2Vs": 100.0,
        "mu_max_cm2Vs": 300000.0,
        "points_per_decade": 40,
        "lorentzian_terms": 6,
        "lorentzian_multi_start": 12,
        "lorentzian_constrained": True,
        "zero_field_window_T": 0.5,
        "alpha_min": 1e-16,
        "alpha_max": 1e-2,
        "noise_source": "residual",
        "discrepancy_factor": 1.1,
        "peak_floor": 0.02,
        "plateau_decades": 3,
        "roundtrip_tolerance": 0.05,
    },
    # Feature 004. The procedure, and which of the two readings of the
    # spectrum runs. `mode` has no default worth defending -- research 004
    # section 4 measures fit mode ahead on one temperature of one sample -- so
    # FR-080 makes the reader choose and this is only the fallback the command
    # line prints a notice about.
    "workflow": {
        # FR-080. "data": the count the data requires and determines, the
        # spectrum's peak count an upper limit. "peaks": the count the peaks
        # give, held, as Liu et al. do. The default needs no evidence beyond
        # the sweep; the other does (research 004 section 4.2).
        "count": "data",
        # The peaks rule has no search to prune, so its single fit is not held
        # to the search's budget: at 5 K no start of the six-carrier fit
        # finished inside 30 s shared by 24 starts. Constraint C16.
        "peaks_multi_start": 12,
        # FR-082. The spectrum's peak count bounds the first search. Past it,
        # the count grows one step at a time while FR-085 keeps choosing the
        # larger combination, and never beyond this many per sign. Constraint
        # C17: at 70 to 90 K the spectrum proposed one carrier of each sign
        # and 2h+2e cut the residual by 2.5 to 5 times, reproducibly.
        "max_per_sign": 4,
        "peaks_fit_budget_s": 120.0,
        "window_factor": 3.0,
        # AC-026 and constraint C20. What an added carrier has to buy. More
        # carriers fit better by construction, so a loose factor lets the
        # largest model set the bar and fails the smallest against it -- which
        # undoes, at the selection step, the reason the spectrum's count is a
        # bound at all.
        "residual_factor": 2.0,
        "spread_max": 0.01,
        "share_min": 0.001,
        "search_multi_start": 12,
        "final_multi_start": 24,
        # AC-040. A coupled refit begins from the answer the pinned refit
        # already found, so further randomised starts re-solve a solved
        # problem; eight of them were the whole difference between three
        # hours and twenty-five minutes (research 005 section 6).
        "smooth_multi_start": 1,
        # FR-109. A count the reader pinned is not a combination the search
        # guessed at, and the budget that prunes the search must not prune it.
        # Measured on this project's sweeps, one starting point of a
        # six-carrier fit: `231` s at 70 K and `52` s at 5 K, against the
        # `2.5` s the search allows it -- so `3h+3e` returned nothing at all at
        # 5, 30 and 70 K, and the reader who asked for it was told nothing.
        # Four starts need `924` s at the worst of those; `1800` leaves a
        # machine two to three times slower than this one enough to finish two,
        # which is where a spread becomes measurable (C18).
        "pinned_multi_start": 4,
        "pinned_fit_budget_s": 1800.0,
        # FR-112. Bands to couple once their counts are pinned.
        "smooth_band": [],
        "fit_budget_s": 30.0,
        "loop_tolerance": 0.01,
        "loop_max_iterations": 10,
        # FR-025 and FR-027. Coupling strengths offered for a pinned band, in
        # the units of `smoothing.lambda_*`. Measured on this project's twelve
        # sweeps over 5 to 90 K: `1e-5` costs 5 % of the residual at the worst
        # sweep, `1e-4` costs 69 %, `1e-3` costs 131 %. None of them is free,
        # which is the point of reporting the price.
        "smoothing_weak": 1e-5,
        "smoothing_normal": 1e-4,
        "smoothing_strong": 1e-3,
        "fixed_counts": {},
    },
    "output": {
        "make_plots": True,
        "plot_dpi": 180,
    },
}

REQUIRED_COLUMN_KEYS = ("T", "B", "rhoxx", "rhoxy")

# Value constraints, by dotted path. Each entry is (predicate, description of
# the admissible set) where the description is machine-readable detail, not a
# sentence for a human.
_POSITIVE = (lambda v: _is_number(v) and v > 0, "positive number")
_NON_NEGATIVE = (lambda v: _is_number(v) and v >= 0, "non-negative number")
_NUMBER = (lambda v: _is_number(v), "number")
_BOOL = (lambda v: isinstance(v, bool), "true or false")
_POSITIVE_INT = (lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1, "integer >= 1")

#: FR-090. Holes and electrons together that a reader may pin at one
#: temperature. The search grows to four carriers per sign; pinning by hand
#: reaches the same and no further, because past it a sweep of ordinary length
#: does not determine the fit whatever the reader intends. One constant, so the
#: command line and the page cannot disagree about it.
MAX_PINNED_CARRIERS = 8


def temperature_range(key: str, path: str) -> tuple[float, float]:
    """One temperature, or a closed range written `low-high`. FR-090.

    FR-090 is about a range -- a series whose model changes underneath it is
    not a series -- so a key that names only one temperature is the special
    case, not the rule.
    """
    pieces = [piece.strip() for piece in str(key).split("-")]
    expected = "a temperature, or a closed range written low-high"
    if len(pieces) > 2 or any(piece == "" for piece in pieces):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, value=key, expected=expected)
    try:
        numbers = [float(piece) for piece in pieces]
    except ValueError:
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, value=key,
                         expected=expected) from None
    low, high = (numbers[0], numbers[-1])
    if high < low:
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, value=key,
                         expected="a range whose first temperature is the lower")
    return low, high


def _resolve_fixed_counts(declared: Any, path: str) -> dict[str, list[int]]:
    """FR-090's pinned counts: `{"<T or low-high>": [holes, electrons]}`.

    The keys are temperatures the reader chose, so unlike every other section
    they cannot be checked against a table of known fields. Until this resolver
    existed the general rule rejected all of them, and FR-090's command-line
    route raised `E_CONFIG_UNKNOWN_FIELD` for every document -- including the
    worked example in the walkthrough. An unchecked mapping is not the
    alternative: a misspelt key that silently pins nothing is the failure this
    guards against.
    """
    if declared is None:
        return {}
    if not isinstance(declared, dict):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, expected="object")
    resolved: dict[str, list[int]] = {}
    for key, value in declared.items():
        where = f"{path}.{key}"
        temperature_range(str(key), where)
        whole = (isinstance(value, (list, tuple)) and len(value) == 2
                 and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                         for v in value))
        if not whole:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=where, value=value,
                             expected="[holes, electrons], whole numbers >= 0")
        total = int(value[0]) + int(value[1])
        if not 1 <= total <= MAX_PINNED_CARRIERS:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=where, value=value,
                             expected=f"1 to {MAX_PINNED_CARRIERS} carriers in total")
        resolved[str(key)] = [int(value[0]), int(value[1])]
    return resolved


#: FR-025. The strengths a band may be coupled at, named rather than numbered
#: so that a document says what it asked for.
SMOOTHING_STRENGTHS = ("weak", "normal", "strong")


def _resolve_smooth_band(declared: Any, path: str) -> list[dict[str, Any]]:
    """FR-112. Bands to couple across temperature, after their counts are pinned.

    `[{"range": "<T or low-high>", "strength": "weak"|"normal"|"strong"}]`.

    It exists because a coupled answer had no form a configuration document
    could carry: the coupling runs under a strategy the procedure never
    selects, so the page could produce an answer the command line could not,
    which FR-107 forbids. A list rather than a mapping, because the order a
    reader coupled things in is part of what they did.
    """
    if declared is None:
        return []
    if not isinstance(declared, list):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, expected="list")
    resolved: list[dict[str, Any]] = []
    for index, entry in enumerate(declared):
        where = f"{path}[{index}]"
        if not isinstance(entry, dict) or set(entry) - {"range", "strength"}:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=where, value=entry,
                             expected="{range, strength}")
        low, high = temperature_range(str(entry.get("range", "")), f"{where}.range")
        strength = entry.get("strength", "normal")
        if strength not in SMOOTHING_STRENGTHS:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{where}.strength",
                             value=strength,
                             expected=" or ".join(SMOOTHING_STRENGTHS))
        resolved.append({"range": str(entry["range"]), "strength": str(strength),
                         "low": low, "high": high})
    return resolved

CONSTRAINTS: dict[str, tuple[Any, str]] = {
    "model.hall_polarity": (lambda v: v in (1, -1, 1.0, -1.0), "+1 or -1"),
    "preprocess.rhoxy_scale": _NUMBER,
    "preprocess.symmetrize_rhoxx": _BOOL,
    "preprocess.antisymmetrize_rhoxy": _BOOL,
    "preprocess.mirror_interpolate": _BOOL,
    "preprocess.mirror_tolerance_T": _NON_NEGATIVE,
    "optimization.fit_mode": (lambda v: v in FIT_MODES, "|".join(FIT_MODES)),
    "optimization.fit_space": (lambda v: v in FIT_SPACES, "|".join(FIT_SPACES)),
    "optimization.weight_rhoxx": _NON_NEGATIVE,
    "optimization.weight_rhoxy": _NON_NEGATIVE,
    "optimization.low_field_weight.enabled": _BOOL,
    "optimization.low_field_weight.alpha": _NON_NEGATIVE,
    "optimization.low_field_weight.B0_T": _POSITIVE,
    "optimization.fit_field_range.enabled": _BOOL,
    "optimization.fit_field_range.abs_min_T": _NON_NEGATIVE,
    "optimization.fit_field_range.abs_max_T": (
        lambda v: v is None or (_is_number(v) and v > 0),
        "positive number or null",
    ),
    "optimization.temperature_strategy": (lambda v: v in STRATEGIES, "|".join(STRATEGIES)),
    "optimization.multi_start": _POSITIVE_INT,
    "optimization.multi_start_log_sigma": _NON_NEGATIVE,
    "optimization.random_seed": (
        lambda v: isinstance(v, int) and not isinstance(v, bool),
        "integer",
    ),
    "optimization.loss": (lambda v: v in LOSSES, "|".join(LOSSES)),
    "optimization.f_scale": _POSITIVE,
    "optimization.max_nfev": _POSITIVE_INT,
    "optimization.fit_budget_s": _NON_NEGATIVE,
    "optimization.global_budget_s": _NON_NEGATIVE,
    "optimization.ftol": _POSITIVE,
    "optimization.xtol": _POSITIVE,
    "optimization.gtol": _POSITIVE,
    "smoothing.enabled": _BOOL,
    "smoothing.order": (lambda v: v in (1, 2), "1 or 2"),
    "smoothing.lambda_density": _NON_NEGATIVE,
    "smoothing.lambda_mobility": _NON_NEGATIVE,
    "smoothing.breaks_K": (
        lambda v: isinstance(v, list) and all(_is_number(x) for x in v),
        "list of numbers",
    ),
    "monotonic_penalty.enabled": _BOOL,
    "monotonic_penalty.lambda": _NON_NEGATIVE,
    "acceptance.r2_rhoxx_min": _NUMBER,
    "acceptance.r2_rhoxy_min": _NUMBER,
    "acceptance.bound_fraction": _NON_NEGATIVE,
    "acceptance.jump_factor": _POSITIVE,
    "acceptance.cost_equivalence": _NON_NEGATIVE,
    "acceptance.parameter_difference": _NON_NEGATIVE,
    "acceptance.residual_runs_z": _NUMBER,
    "acceptance.excluded_rms_ratio": _POSITIVE,
    "acceptance.condition_number_max": _POSITIVE,
    "uncertainty.enabled": _BOOL,
    "uncertainty.resamples": _POSITIVE_INT,
    "uncertainty.block_length": _POSITIVE_INT,
    "uncertainty.interval_fraction": (
        lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 < v < 1.0,
        "a fraction strictly between 0 and 1",
    ),
    "uncertainty.seed": (
        lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool)),
        "an integer or null",
    ),
    "discriminants.harmonic_tolerance": _NON_NEGATIVE,
    "discriminants.parity_threshold": _NON_NEGATIVE,
    "spectrum.enabled": _BOOL,
    "spectrum.mu_min_cm2Vs": _POSITIVE,
    "spectrum.mu_max_cm2Vs": _POSITIVE,
    "spectrum.points_per_decade": _POSITIVE_INT,
    "spectrum.lorentzian_terms": (
        lambda v: isinstance(v, int) and not isinstance(v, bool) and 2 <= v <= 12,
        "an integer from 2 to 12",
    ),
    "spectrum.lorentzian_multi_start": _POSITIVE_INT,
    "spectrum.lorentzian_constrained": _BOOL,
    "spectrum.zero_field_window_T": _POSITIVE,
    "spectrum.alpha_min": _POSITIVE,
    "spectrum.alpha_max": _POSITIVE,
    "spectrum.noise_source": (
        lambda v: v == "residual" or (
            isinstance(v, list) and len(v) == 2
            and all(_is_number(x) and x > 0 for x in v)
        ),
        "the word residual, or a pair of positive numbers",
    ),
    "spectrum.discrepancy_factor": _POSITIVE,
    "spectrum.peak_floor": _NON_NEGATIVE,
    "spectrum.plateau_decades": _POSITIVE_INT,
    "spectrum.roundtrip_tolerance": _POSITIVE,
    "workflow.count": (
        lambda v: v in ("data", "peaks"),
        "either data or peaks",
    ),
    "workflow.smoothing_weak": _NON_NEGATIVE,
    "workflow.smoothing_normal": _NON_NEGATIVE,
    "workflow.smoothing_strong": _NON_NEGATIVE,
    "workflow.peaks_multi_start": _POSITIVE_INT,
    "workflow.max_per_sign": _POSITIVE_INT,
    "workflow.peaks_fit_budget_s": _NON_NEGATIVE,
    "workflow.window_factor": _POSITIVE,
    "workflow.residual_factor": _POSITIVE,
    "workflow.spread_max": _POSITIVE,
    "workflow.share_min": _NON_NEGATIVE,
    "workflow.search_multi_start": _POSITIVE_INT,
    "workflow.final_multi_start": _POSITIVE_INT,
    "workflow.smooth_multi_start": _POSITIVE_INT,
    "workflow.pinned_multi_start": _POSITIVE_INT,
    "workflow.pinned_fit_budget_s": _NON_NEGATIVE,
    "workflow.fit_budget_s": _NON_NEGATIVE,
    "workflow.loop_tolerance": _POSITIVE,
    "workflow.loop_max_iterations": _POSITIVE_INT,
    "output.make_plots": _BOOL,
    "output.plot_dpi": _POSITIVE_INT,
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# --------------------------------------------------------------- structures

@dataclass(frozen=True)
class CarrierSpec:
    """One declared carrier. `data-model.md` section 1.1.

    Article V: every numeric field carries its unit in its name, because these
    are the boundary units and not SI.
    """

    name: str
    kind: str
    n_init_cm3: float
    n_min_cm3: float
    n_max_cm3: float
    mu_init_cm2Vs: float
    mu_min_cm2Vs: float
    mu_max_cm2Vs: float
    smooth_density: bool = True
    smooth_mobility: bool = True
    monotonic_density: str = "none"
    monotonic_mobility: str = "none"

    @property
    def sign(self) -> float:
        return sign_of_kind(self.kind)


@dataclass(frozen=True)
class ResolvedConfig:
    """Every value the run used, defaults included. FR-037."""

    schema_version: str
    columns: dict[str, str]
    carriers: tuple[CarrierSpec, ...]
    model: dict[str, Any]
    preprocess: dict[str, Any]
    optimization: dict[str, Any]
    smoothing: dict[str, Any]
    monotonic_penalty: dict[str, Any]
    acceptance: dict[str, Any]
    uncertainty: dict[str, Any]
    discriminants: dict[str, Any]
    spectrum: dict[str, Any]
    workflow: dict[str, Any]
    output: dict[str, Any]
    initial_by_temperature: dict[str, Any] = field(default_factory=dict)
    overrides_by_temperature: dict[str, Any] = field(default_factory=dict)

    @property
    def n_free_parameters(self) -> int:
        """Two per carrier: a density and a mobility."""
        return 2 * len(self.carriers)

    @property
    def n_channels(self) -> int:
        """How many residuals each record contributes. FR-006."""
        return 2 if self.optimization["fit_mode"] == "both" else 1

    def carrier_named(self, name: str) -> CarrierSpec:
        for carrier in self.carriers:
            if carrier.name == name:
                return carrier
        raise MbfitError("E_CONFIG_UNKNOWN_CARRIER", name=name)

    def as_document(self) -> dict[str, Any]:
        """The configuration as a document that reproduces this run exactly."""
        return {
            "schema_version": self.schema_version,
            "columns": dict(self.columns),
            "carriers": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "density": {"init": c.n_init_cm3, "min": c.n_min_cm3, "max": c.n_max_cm3},
                    "mobility": {
                        "init": c.mu_init_cm2Vs,
                        "min": c.mu_min_cm2Vs,
                        "max": c.mu_max_cm2Vs,
                    },
                    "smooth_density": c.smooth_density,
                    "smooth_mobility": c.smooth_mobility,
                    "monotonic_density": c.monotonic_density,
                    "monotonic_mobility": c.monotonic_mobility,
                }
                for c in self.carriers
            ],
            "initial_by_temperature": self.initial_by_temperature,
            "overrides_by_temperature": self.overrides_by_temperature,
            "model": dict(self.model),
            "preprocess": dict(self.preprocess),
            "optimization": _deep_copy(self.optimization),
            "smoothing": _deep_copy(self.smoothing),
            "monotonic_penalty": dict(self.monotonic_penalty),
            "acceptance": dict(self.acceptance),
            "uncertainty": dict(self.uncertainty),
            "discriminants": dict(self.discriminants),
            "spectrum": _deep_copy(self.spectrum),
            "workflow": _deep_copy(self.workflow),
            "output": dict(self.output),
        }


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


# ------------------------------------------------------------------ loading

def load_document(path: str | pathlib.Path) -> dict[str, Any]:
    """Read the configuration document. Raises E_CONFIG_UNREADABLE."""
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise MbfitError("E_CONFIG_UNREADABLE", path=str(path), reason=type(error).__name__) from None
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise MbfitError(
            "E_CONFIG_UNREADABLE", path=str(path), line=error.lineno, column=error.colno
        ) from None
    if not isinstance(document, dict):
        raise MbfitError("E_CONFIG_UNREADABLE", path=str(path), reason="not_an_object")
    return document


# --------------------------------------------------------------- validation

def _merge_section(name: str, declared: Any, defaults: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Fill defaults into one section, rejecting unknown or mistyped fields."""
    if declared is None:
        declared = {}
    if not isinstance(declared, dict):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=prefix or name, expected="object")

    for key in declared:
        if key not in defaults:
            raise MbfitError(
                "E_CONFIG_UNKNOWN_FIELD",
                path=f"{prefix}.{key}" if prefix else key,
                known=sorted(defaults),
            )

    resolved: dict[str, Any] = {}
    for key, default in defaults.items():
        path = f"{prefix}.{key}" if prefix else key
        # Before the type of the default is looked at: a free-form section is
        # not always a mapping. `workflow.smooth_band` is a list, and while
        # this branch was reached only for mappings its resolver was skipped
        # and every entry passed unchecked.
        free_form = FREE_FORM_SECTIONS.get(path)
        if free_form is not None:
            resolved[key] = free_form(declared.get(key), path)
            continue
        if isinstance(default, dict):
            resolved[key] = _merge_section(key, declared.get(key), default, path)
            continue
        value = declared.get(key, default)
        constraint = CONSTRAINTS.get(path)
        if constraint is not None and not constraint[0](value):
            raise MbfitError("E_CONFIG_BAD_VALUE", path=path, value=value, expected=constraint[1])
        resolved[key] = value
    return resolved


#: Settings whose contents the reader invents -- keys in one case, list
#: entries in the other -- each with the resolver that checks its shape.
#: Walking one with the general rule rejects everything the reader wrote.
FREE_FORM_SECTIONS: dict[str, Any] = {
    "workflow.fixed_counts": _resolve_fixed_counts,
    "workflow.smooth_band": _resolve_smooth_band,
}


def _resolve_columns(declared: Any) -> dict[str, str]:
    if declared is None:
        raise MbfitError("E_CONFIG_MISSING_FIELD", path="columns")
    if not isinstance(declared, dict):
        raise MbfitError("E_CONFIG_BAD_VALUE", path="columns", expected="object")
    for key in declared:
        if key not in REQUIRED_COLUMN_KEYS:
            raise MbfitError("E_CONFIG_UNKNOWN_FIELD", path=f"columns.{key}", known=list(REQUIRED_COLUMN_KEYS))
    missing = [key for key in REQUIRED_COLUMN_KEYS if key not in declared]
    if missing:
        raise MbfitError("E_CONFIG_MISSING_FIELD", path="columns", missing=missing)
    for key, value in declared.items():
        if not isinstance(value, str) or not value:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"columns.{key}", value=value, expected="non-empty text")
    return {key: declared[key] for key in REQUIRED_COLUMN_KEYS}


_CARRIER_FIELDS = {
    "name",
    "kind",
    "density",
    "mobility",
    "smooth_density",
    "smooth_mobility",
    "monotonic_density",
    "monotonic_mobility",
}
_BOUND_FIELDS = {"init", "min", "max"}


def _resolve_bounds(declared: Any, path: str) -> tuple[float, float, float]:
    """`{init, min, max}` for one quantity, with FR-014 and FR-015 enforced."""
    if not isinstance(declared, dict):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, expected="object with init, min, max")
    for key in declared:
        if key not in _BOUND_FIELDS:
            raise MbfitError("E_CONFIG_UNKNOWN_FIELD", path=f"{path}.{key}", known=sorted(_BOUND_FIELDS))
    missing = sorted(_BOUND_FIELDS - set(declared))
    if missing:
        raise MbfitError("E_CONFIG_MISSING_FIELD", path=path, missing=missing)
    for key in _BOUND_FIELDS:
        if not _is_number(declared[key]):
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.{key}", value=declared[key], expected="number")

    init, low, high = float(declared["init"]), float(declared["min"]), float(declared["max"])
    # NR-001 and FR-014. A non-positive lower bound would put zero inside the
    # admissible domain, which the logarithm of NR-002 cannot represent.
    if low <= 0.0 or high <= 0.0 or low > high:
        raise MbfitError("E_CONFIG_BOUNDS_INVALID", path=path, min=low, max=high)
    # FR-015: rejected before fitting begins, naming what is wrong.
    if not (low <= init <= high):
        raise MbfitError("E_CONFIG_INIT_OUT_OF_BOUNDS", path=path, init=init, min=low, max=high)
    return init, low, high


def _resolve_carriers(declared: Any) -> tuple[CarrierSpec, ...]:
    if declared is None:
        raise MbfitError("E_CONFIG_MISSING_FIELD", path="carriers")
    if not isinstance(declared, list):
        raise MbfitError("E_CONFIG_BAD_VALUE", path="carriers", expected="list")
    if not declared:
        raise MbfitError("E_CONFIG_NO_CARRIERS")

    carriers: list[CarrierSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(declared):
        path = f"carriers[{index}]"
        if not isinstance(entry, dict):
            raise MbfitError("E_CONFIG_BAD_VALUE", path=path, expected="object")
        for key in entry:
            if key not in _CARRIER_FIELDS:
                raise MbfitError("E_CONFIG_UNKNOWN_FIELD", path=f"{path}.{key}", known=sorted(_CARRIER_FIELDS))
        for required in ("name", "kind", "density", "mobility"):
            if required not in entry:
                raise MbfitError("E_CONFIG_MISSING_FIELD", path=path, missing=[required])

        name = entry["name"]
        if not isinstance(name, str) or not name:
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.name", value=name, expected="non-empty text")
        if name in seen:
            raise MbfitError("E_CONFIG_DUPLICATE_CARRIER", name=name)
        seen.add(name)

        kind = entry["kind"]
        if kind not in CARRIER_KINDS:
            raise MbfitError("E_CONFIG_BAD_CARRIER_KIND", name=name, kind=kind)

        n_init, n_min, n_max = _resolve_bounds(entry["density"], f"{path}.density")
        mu_init, mu_min, mu_max = _resolve_bounds(entry["mobility"], f"{path}.mobility")

        flags = {}
        for flag in ("smooth_density", "smooth_mobility"):
            value = entry.get(flag, True)
            if not isinstance(value, bool):
                raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.{flag}", value=value, expected="true or false")
            flags[flag] = value
        directions = {}
        for direction in ("monotonic_density", "monotonic_mobility"):
            value = entry.get(direction, "none")
            if value not in MONOTONIC:
                raise MbfitError(
                    "E_CONFIG_BAD_VALUE", path=f"{path}.{direction}", value=value, expected="|".join(MONOTONIC)
                )
            directions[direction] = value

        carriers.append(
            CarrierSpec(
                name=name,
                kind=kind,
                n_init_cm3=n_init,
                n_min_cm3=n_min,
                n_max_cm3=n_max,
                mu_init_cm2Vs=mu_init,
                mu_min_cm2Vs=mu_min,
                mu_max_cm2Vs=mu_max,
                **flags,
                **directions,
            )
        )
    return tuple(carriers)


def _resolve_by_temperature(declared: Any, path: str, names: set[str], allow_bounds: bool) -> dict[str, Any]:
    """`initial_by_temperature` (FR-016) or `overrides_by_temperature` (FR-054)."""
    if declared is None:
        return {}
    if not isinstance(declared, dict):
        raise MbfitError("E_CONFIG_BAD_VALUE", path=path, expected="object keyed by temperature")

    resolved: dict[str, Any] = {}
    for key, entry in declared.items():
        try:
            float(key)
        except (TypeError, ValueError):
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.{key}", value=key, expected="temperature") from None
        if not isinstance(entry, dict):
            raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.{key}", expected="object keyed by carrier")
        for name, quantities in entry.items():
            if name not in names:
                raise MbfitError("E_CONFIG_UNKNOWN_CARRIER", path=f"{path}.{key}.{name}", name=name)
            if not isinstance(quantities, dict):
                raise MbfitError("E_CONFIG_BAD_VALUE", path=f"{path}.{key}.{name}", expected="object")
            for quantity, value in quantities.items():
                where = f"{path}.{key}.{name}.{quantity}"
                if quantity not in ("density", "mobility"):
                    raise MbfitError("E_CONFIG_UNKNOWN_FIELD", path=where, known=["density", "mobility"])
                if allow_bounds:
                    if not isinstance(value, dict):
                        raise MbfitError("E_CONFIG_BAD_VALUE", path=where, expected="object with init, min or max")
                    for bound_key, bound_value in value.items():
                        if bound_key not in _BOUND_FIELDS:
                            raise MbfitError(
                                "E_CONFIG_UNKNOWN_FIELD", path=f"{where}.{bound_key}", known=sorted(_BOUND_FIELDS)
                            )
                        if not _is_number(bound_value) or bound_value <= 0.0:
                            raise MbfitError(
                                "E_CONFIG_BAD_VALUE", path=f"{where}.{bound_key}", value=bound_value,
                                expected="positive number",
                            )
                elif not _is_number(value) or value <= 0.0:
                    raise MbfitError("E_CONFIG_BAD_VALUE", path=where, value=value, expected="positive number")
        resolved[key] = _deep_copy(entry)
    return resolved


def resolve(document: dict[str, Any]) -> ResolvedConfig:
    """Validate a configuration document and fill in every default."""
    if not isinstance(document, dict):
        raise MbfitError("E_CONFIG_UNREADABLE", reason="not_an_object")

    # `_run` is provenance the program writes and never reads: the strategy
    # that ran, the temperatures it saw, the seed, the conditioning. It is
    # accepted and ignored so that FR-037 holds -- the emitted document has to
    # feed straight back in -- while the underscore says it is not a setting.
    known_top = {
        "schema_version", "columns", "carriers",
        "initial_by_temperature", "overrides_by_temperature", "_run",
    }
    known_top |= set(DEFAULTS)
    for key in document:
        if key not in known_top:
            raise MbfitError("E_CONFIG_UNKNOWN_FIELD", path=key, known=sorted(known_top))

    version = document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise MbfitError("E_CONFIG_SCHEMA_VERSION", found=version, supported=SCHEMA_VERSION)

    columns = _resolve_columns(document.get("columns"))
    carriers = _resolve_carriers(document.get("carriers"))
    names = {carrier.name for carrier in carriers}

    sections = {
        name: _merge_section(name, document.get(name), defaults, name)
        for name, defaults in DEFAULTS.items()
    }

    # FR-024 and FR-025: seeding and coupling are different things. A penalty
    # coupling the temperatures can only act when the temperatures are one
    # problem, so asking for one with any other strategy is a contradiction,
    # and a contradiction is refused rather than silently resolved.
    strategy = sections["optimization"]["temperature_strategy"]
    coupling_wanted = sections["smoothing"]["enabled"] or sections["monotonic_penalty"]["enabled"]
    if coupling_wanted and strategy != "global_smooth":
        raise MbfitError(
            "E_CONFIG_COUPLING_WITHOUT_GLOBAL",
            strategy=strategy,
            smoothing=sections["smoothing"]["enabled"],
            monotonic=sections["monotonic_penalty"]["enabled"],
        )

    spectrum = sections["spectrum"]
    if spectrum["mu_min_cm2Vs"] >= spectrum["mu_max_cm2Vs"]:
        raise MbfitError(
            "E_CONFIG_BAD_VALUE",
            path="spectrum.mu_min_cm2Vs",
            value=[spectrum["mu_min_cm2Vs"], spectrum["mu_max_cm2Vs"]],
            expected="mu_min_cm2Vs < mu_max_cm2Vs",
        )
    if spectrum["alpha_min"] > spectrum["alpha_max"]:
        raise MbfitError(
            "E_CONFIG_BAD_VALUE",
            path="spectrum.alpha_min",
            value=[spectrum["alpha_min"], spectrum["alpha_max"]],
            expected="alpha_min <= alpha_max",
        )

    window = sections["optimization"]["fit_field_range"]
    if window["enabled"] and window["abs_max_T"] is not None and window["abs_min_T"] >= window["abs_max_T"]:
        raise MbfitError(
            "E_CONFIG_BAD_VALUE",
            path="optimization.fit_field_range",
            value=[window["abs_min_T"], window["abs_max_T"]],
            expected="abs_min_T < abs_max_T",
        )

    return ResolvedConfig(
        schema_version=SCHEMA_VERSION,
        columns=columns,
        carriers=carriers,
        initial_by_temperature=_resolve_by_temperature(
            document.get("initial_by_temperature"), "initial_by_temperature", names, allow_bounds=False
        ),
        overrides_by_temperature=_resolve_by_temperature(
            document.get("overrides_by_temperature"), "overrides_by_temperature", names, allow_bounds=True
        ),
        **sections,
    )


def validate_against_temperatures(config: ResolvedConfig, temperatures) -> None:
    """Checks that need the data. Raises E_CONFIG_BREAK_OUTSIDE_RANGE.

    A coupling break outside the measured range cuts nothing, which means the
    document says something the run cannot honour. FR-053.
    """
    values = sorted(float(t) for t in temperatures)
    if not values:
        return
    for break_temperature in config.smoothing["breaks_K"]:
        if not (values[0] < float(break_temperature) < values[-1]):
            raise MbfitError(
                "E_CONFIG_BREAK_OUTSIDE_RANGE",
                value=float(break_temperature),
                lowest=values[0],
                highest=values[-1],
            )


def disable_soft_priors(config: ResolvedConfig) -> ResolvedConfig:
    """FR-057. Every soft prior off, every hard constraint untouched.

    The soft priors are ledger entries C3 to C6: the temperature coupling, the
    monotonic expectation, the low-field emphasis and the robust
    down-weighting. The declared bounds (C2) and the field window (C7) stay,
    because they declare the admissible domain rather than a preference
    within it.

    The result is a configuration in its own right, so writing it out under
    FR-037 records what was in force rather than what was declared, and
    feeding it back reproduces the run without the switch.
    """
    document = config.as_document()
    document["smoothing"]["enabled"] = False
    document["monotonic_penalty"]["enabled"] = False
    document["optimization"]["low_field_weight"]["enabled"] = False
    document["optimization"]["loss"] = "linear"
    if document["optimization"]["temperature_strategy"] == "global_smooth":
        # Nothing now couples the temperatures, so the global problem is the
        # independent one solved in a single, slower pass. Left as declared:
        # the strategy is the user's statement about how to search, not a
        # prior about the sample.
        pass
    return resolve(document)
