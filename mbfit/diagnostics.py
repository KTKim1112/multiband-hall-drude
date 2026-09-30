"""The evidence against trusting the answer.

FR-042 to FR-048, FR-055 and FR-056. Constitution Article VI: a result never
leaves without the violations detected alongside it, because the classical
independent-carrier model returns a number for data that breaks every one of
its assumptions, and a high R-squared is not evidence that the carrier
decomposition is unique.

FR-048 shapes every entry here. A diagnostic states the quantity it measured,
the threshold it crossed, and where that threshold came from, so a reader can
disagree with the threshold rather than only with the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import ResolvedConfig
from .core import harmonics
from .core.canonical import canonical_permutation, split_parameters
from .core.metrics import runs_test_z
from .dataio import Dataset
from .fitting import RunResult, model_resistivity, signs

WARNING = "warning"
NOTE = "note"

# Below this, two costs are the same answer whatever their ratio. The cost is
# half the sum of squared residuals normalised by the channel scale, so 1e-16
# means every residual sits below about 1e-8 of the signal: further apart in
# ratio, indistinguishable in fact. Research 4.6 recorded why this floor is
# needed, having measured a best cost of 2e-28 on noiseless synthetic data,
# where AC-005 compares relatively and reports nothing.
NEGLIGIBLE_COST = 1e-16


@dataclass(frozen=True)
class Diagnostic:
    """One detected violation. `data-model.md` section 1.6.

    No sentence for a human appears here. Article IV: the Korean wording lives
    in `messages.py`, keyed by `code`.
    """

    code: str
    severity: str
    where: dict[str, Any] = field(default_factory=dict)
    measured: Any = None
    threshold: Any = None
    threshold_source: str | None = None

    def as_row(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "where": ", ".join(f"{k}={v}" for k, v in self.where.items()),
            "measured": self.measured,
            "threshold": self.threshold,
            "threshold_source": self.threshold_source or "",
        }


# ------------------------------------------------------------- intake, FR-005

def intake(dataset: Dataset) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    if dataset.n_records_dropped:
        found.append(
            Diagnostic(
                "D_RECORDS_DROPPED",
                NOTE,
                measured=dataset.n_records_dropped,
                threshold=0,
                threshold_source="none",
            )
        )
    for group in dataset.groups:
        if group.n_mirror_absent:
            found.append(
                Diagnostic(
                    "D_MIRROR_ABSENT",
                    NOTE,
                    where={"T_K": group.T_K},
                    measured=group.n_mirror_absent,
                    threshold=0,
                    threshold_source="none",
                )
            )
    return found


# ---------------------------------------------------------- FR-065 and FR-066

def parity_violation(dataset: Dataset, config: ResolvedConfig) -> list[Diagnostic]:
    """How much of each channel had the wrong parity before symmetrising.

    Measured at intake, because the symmetrisation of FR-008 and FR-009 is
    what removes it. A sweep of one polarity cannot be asked the question at
    all, and FR-066 requires that to be reported rather than passed over: the
    admixture is still in the data, it simply was not measurable.
    """
    threshold = float(config.discriminants["parity_threshold"])
    found: list[Diagnostic] = []
    for group in dataset.groups:
        if not group.both_polarities:
            found.append(
                Diagnostic(
                    "D_SINGLE_POLARITY",
                    WARNING,
                    where={"T_K": group.T_K},
                    measured=None,
                    threshold=None,
                    threshold_source="FR-066",
                )
            )
            continue
        for channel, value in (
            ("rhoxx", group.parity_rhoxx),
            ("rhoxy", group.parity_rhoxy),
        ):
            if value is not None and value > threshold:
                found.append(
                    Diagnostic(
                        "D_PARITY_VIOLATION",
                        WARNING,
                        where={"T_K": group.T_K, "channel": channel},
                        measured=value,
                        threshold=threshold,
                        threshold_source="AC-015",
                    )
                )
    return found


# ------------------------------------------------------------------- FR-063

def harmonic_ladder(result: RunResult) -> list[Diagnostic]:
    """Could this carrier set be one non-circular orbit? Research 002 section 4.

    Reported only when all three conditions hold, because any one of them
    alone is ordinary. The measured value is the number of conditions met, so
    a reader who wants the near misses can read `harmonics_vs_T.csv` rather
    than have them announced as warnings.
    """
    tolerance = float(result.config.discriminants["harmonic_tolerance"])
    found: list[Diagnostic] = []
    for fit in result.fits:
        params = fit.params_canonical
        verdict = harmonics.verdict(
            params[0::2], params[1::2], signs(fit.specs), tolerance
        )
        if verdict["is_ladder"]:
            found.append(
                Diagnostic(
                    "D_HARMONIC_LADDER",
                    WARNING,
                    where={"T_K": fit.T_K},
                    measured=3,
                    threshold=3,
                    threshold_source="AC-014",
                )
            )
    return found


# --------------------------------------------------------- fit quality, AC-001

def fit_quality(result: RunResult) -> list[Diagnostic]:
    acceptance = result.config.acceptance
    found: list[Diagnostic] = []
    for fit in result.fits:
        for channel, value, floor, source in (
            ("rhoxx", fit.r2_rhoxx, acceptance["r2_rhoxx_min"], "AC-001"),
            ("rhoxy", fit.r2_rhoxy, acceptance["r2_rhoxy_min"], "AC-002"),
        ):
            if np.isfinite(value) and value < floor:
                found.append(
                    Diagnostic(
                        "D_R2_BELOW",
                        WARNING,
                        where={"T_K": fit.T_K, "channel": channel},
                        measured=float(value),
                        threshold=float(floor),
                        threshold_source=source,
                    )
                )
    return found


# ------------------------------------------------------------- bounds, FR-043

def at_bound(result: RunResult) -> list[Diagnostic]:
    fraction = result.config.acceptance["bound_fraction"]
    found: list[Diagnostic] = []
    for fit in result.fits:
        for index, spec in enumerate(fit.specs):
            for offset, quantity, low, high in (
                (0, "density", spec.n_min_cm3, spec.n_max_cm3),
                (1, "mobility", spec.mu_min_cm2Vs, spec.mu_max_cm2Vs),
            ):
                position = 2 * index + offset
                if fit.at_bound_low[position] or fit.at_bound_high[position]:
                    which = "min" if fit.at_bound_low[position] else "max"
                    found.append(
                        Diagnostic(
                            "D_AT_BOUND",
                            WARNING,
                            where={
                                "T_K": fit.T_K,
                                "carrier": spec.name,
                                "quantity": quantity,
                                "bound": which,
                            },
                            measured=float(fit.params[position]),
                            threshold=float(low if which == "min" else high),
                            threshold_source="AC-003",
                        )
                    )
    return found


# ------------------------------------------- jumps and relabelling, FR-044/047

def jumps_and_swaps(result: RunResult) -> list[Diagnostic]:
    """Evaluated together, because a relabelling looks exactly like a jump.

    Research 4.4 measured how freely the labels move, and PM-003 makes such an
    exchange free of cost. Reporting a jump without the swap beside it
    misleads; the comparison is therefore made on the canonical order, and the
    swap is reported separately.
    """
    if len(result.fits) < 2:
        return []
    factor = result.config.acceptance["jump_factor"]
    sign = signs(result.fits[0].specs)
    found: list[Diagnostic] = []

    for position in result.order_changes:
        found.append(
            Diagnostic(
                "D_LABEL_SWAP",
                NOTE,
                where={
                    "T_K": result.fits[position].T_K,
                    "next_T_K": result.fits[position + 1].T_K,
                },
                measured="canonical order changed",
                threshold="none",
                threshold_source="none",
            )
        )

    for index in range(1, len(result.fits)):
        lower, upper = result.fits[index - 1], result.fits[index]
        order = canonical_permutation(upper.params, sign)
        for carrier_index, spec in enumerate(lower.specs):
            for offset, quantity in ((0, "density"), (1, "mobility")):
                before = lower.params_canonical[2 * carrier_index + offset]
                after = upper.params_canonical[2 * carrier_index + offset]
                ratio = max(after / before, before / after)
                if ratio > factor:
                    found.append(
                        Diagnostic(
                            "D_JUMP",
                            WARNING,
                            where={
                                "T_K": lower.T_K,
                                "next_T_K": upper.T_K,
                                "canonical_index": carrier_index,
                                "quantity": quantity,
                            },
                            measured=float(ratio),
                            threshold=float(factor),
                            threshold_source="AC-004",
                        )
                    )
        del order
    return found


# ------------------------------------------------------- non-uniqueness, FR-045

def non_unique(result: RunResult) -> list[Diagnostic]:
    """Distinct canonical solutions of indistinguishable cost. AC-005, AC-006.

    Compared after canonicalisation only. Research 4.4: index by index, 190
    solutions of one fit spread by a factor of 113 while every one of them was
    the same solution relabelled. A naive comparison reports a hundredfold
    non-uniqueness on a problem that has none.
    """
    acceptance = result.config.acceptance
    equivalence = acceptance["cost_equivalence"]
    difference = acceptance["parameter_difference"]
    found: list[Diagnostic] = []

    for fit in result.fits:
        if len(fit.starts) < 2:
            continue
        sign = signs(fit.specs)
        best = min(start.cost for start in fit.starts)
        rivals = []
        for start in fit.starts:
            relatively_close = start.cost <= best * (1.0 + equivalence) + 1e-300
            both_negligible = start.cost <= NEGLIGIBLE_COST
            if not (relatively_close or both_negligible):
                continue
            permutation = canonical_permutation(start.params, sign)
            n, mu = split_parameters(start.params)
            rivals.append(np.concatenate([n[permutation], mu[permutation]]))
        if len(rivals) < 2:
            continue
        block = np.vstack(rivals)
        spread = np.max(np.abs(block / block[0] - 1.0))
        if spread > difference:
            found.append(
                Diagnostic(
                    "D_NON_UNIQUE",
                    WARNING,
                    where={"T_K": fit.T_K, "n_equivalent_starts": len(rivals)},
                    measured=float(spread),
                    threshold=float(difference),
                    threshold_source="AC-006",
                )
            )
    return found


# ------------------------------------------------- residual structure, FR-046

def residual_structure(result: RunResult, dataset: Dataset) -> list[Diagnostic]:
    floor = result.config.acceptance["residual_runs_z"]
    polarity = float(result.config.model["hall_polarity"])
    found: list[Diagnostic] = []

    for fit, group in zip(result.fits, dataset.groups):
        sign = signs(fit.specs)
        model_xx, model_xy = model_resistivity(group.B_T, fit.params, sign, polarity)
        inside = group.in_fit_window
        for channel, measured, modelled in (
            ("rhoxx", group.rhoxx_uohmcm, model_xx),
            ("rhoxy", group.rhoxy_uohmcm, model_xy),
        ):
            score = runs_test_z((measured - modelled)[inside])
            if np.isfinite(score) and score < floor:
                found.append(
                    Diagnostic(
                        "D_RESIDUAL_STRUCTURE",
                        WARNING,
                        where={"T_K": fit.T_K, "channel": channel},
                        measured=float(score),
                        threshold=float(floor),
                        threshold_source="AC-007",
                    )
                )
            elif score == float("-inf"):
                found.append(
                    Diagnostic(
                        "D_RESIDUAL_STRUCTURE",
                        WARNING,
                        where={"T_K": fit.T_K, "channel": channel},
                        measured="constant sign",
                        threshold=float(floor),
                        threshold_source="AC-007",
                    )
                )
    return found


# -------------------------------------------------------- slow carriers, FR-048

def low_mu_b(result: RunResult, dataset: Dataset) -> list[Diagnostic]:
    """A carrier whose `mu B` never reaches 1 over the measured range.

    Research 4.3 measured a 35 % error on exactly such a carrier while
    R-squared stayed above 0.9995. Low-field data constrains a few moments of
    the carrier distribution, not the individual parameters, and a carrier is
    resolved as an individual only where its own `mu B` approaches 1.
    """
    found: list[Diagnostic] = []
    for fit, group in zip(result.fits, dataset.groups):
        admitted = group.B_T[group.in_fit_window]
        if admitted.size == 0:
            continue
        largest_field = float(np.max(np.abs(admitted)))
        for index, spec in enumerate(fit.specs):
            mu_si = fit.params[2 * index + 1] * 1e-4
            mu_B = mu_si * largest_field
            if mu_B < 1.0:
                found.append(
                    Diagnostic(
                        "D_LOW_MU_B",
                        WARNING,
                        where={"T_K": fit.T_K, "carrier": spec.name},
                        measured=float(mu_B),
                        threshold=1.0,
                        threshold_source="research 4.3",
                    )
                )
    return found


# ------------------------------------------------- the field window, FR-049/051

def field_window(result: RunResult, dataset: Dataset) -> list[Diagnostic]:
    window = result.config.optimization["fit_field_range"]
    if not window["enabled"]:
        return []
    ratio_limit = result.config.acceptance["excluded_rms_ratio"]
    found: list[Diagnostic] = []

    excluded = sum(group.n_records - group.n_in_window for group in dataset.groups)
    found.append(
        Diagnostic(
            "D_FIELD_RANGE_ACTIVE",
            NOTE,
            where={"abs_min_T": window["abs_min_T"], "abs_max_T": window["abs_max_T"]},
            measured=excluded,
            threshold="none",
            threshold_source="none",
        )
    )
    for fit in result.fits:
        if fit.rmse_outside is None or fit.rmse_rhoxx <= 0.0:
            continue
        ratio = fit.rmse_outside / fit.rmse_rhoxx
        if ratio > ratio_limit:
            found.append(
                Diagnostic(
                    "D_EXCLUDED_MISMATCH",
                    WARNING,
                    where={"T_K": fit.T_K},
                    measured=float(ratio),
                    threshold=float(ratio_limit),
                    threshold_source="AC-009",
                )
            )
    return found


# ------------------------------------------------------- conditioning, FR-055

def conditioning(result: RunResult) -> list[Diagnostic]:
    """The one diagnostic that measures directly what the others infer.

    FR-043 needs a parameter to have reached a bound, FR-044 two adjacent
    temperatures, FR-045 a repeated search, FR-047 a relabelling. This needs
    none of them, and comes from the converged fit at no extra cost.
    """
    limit = result.config.acceptance["condition_number_max"]
    found: list[Diagnostic] = []
    for fit in result.fits:
        if fit.condition_number > limit:
            found.append(
                Diagnostic(
                    "D_ILL_CONDITIONED",
                    WARNING,
                    where={"T_K": fit.T_K},
                    measured=float(fit.condition_number),
                    threshold=float(limit),
                    threshold_source="AC-010",
                )
            )
    return found


# -------------------------------------------------------------- FR-054, FR-056

def bound_overrides(result: RunResult) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for fit in result.fits:
        for record in fit.overrides:
            found.append(
                Diagnostic(
                    "D_BOUND_OVERRIDE",
                    WARNING,
                    where={
                        "T_K": record["T_K"],
                        "carrier": record["carrier"],
                        "quantity": record["quantity"],
                        "field": record["field"],
                        "source": record["source"],
                    },
                    measured=record["override"],
                    threshold=record["default"],
                    threshold_source="none",
                )
            )
    return found


def priors(config: ResolvedConfig, declared: ResolvedConfig | None = None) -> list[Diagnostic]:
    """Every soft prior in force announces itself. FR-056 and FR-057.

    The field window has done this since FR-049; there is no reason for a
    penalty to be quieter than a truncation. `declared` is the configuration
    before `--no-priors` stripped it, when the switch was used.
    """
    found: list[Diagnostic] = []

    if config.smoothing["enabled"]:
        found.append(
            Diagnostic(
                "D_PRIORS_ACTIVE",
                NOTE,
                where={"prior": "temperature_coupling", "order": config.smoothing["order"],
                       "breaks_K": tuple(config.smoothing["breaks_K"])},
                measured=(config.smoothing["lambda_density"], config.smoothing["lambda_mobility"]),
                threshold="none",
                threshold_source="ledger C3",
            )
        )
    if config.monotonic_penalty["enabled"]:
        directions = {
            c.name: (c.monotonic_density, c.monotonic_mobility)
            for c in config.carriers
            if c.monotonic_density != "none" or c.monotonic_mobility != "none"
        }
        found.append(
            Diagnostic(
                "D_PRIORS_ACTIVE",
                NOTE,
                where={"prior": "monotonic", "directions": directions},
                measured=config.monotonic_penalty["lambda"],
                threshold="none",
                threshold_source="ledger C4",
            )
        )
    if config.optimization["low_field_weight"]["enabled"]:
        emphasis = config.optimization["low_field_weight"]
        found.append(
            Diagnostic(
                "D_PRIORS_ACTIVE",
                NOTE,
                where={"prior": "low_field_emphasis", "B0_T": emphasis["B0_T"]},
                measured=emphasis["alpha"],
                threshold="none",
                threshold_source="ledger C5",
            )
        )
    if config.optimization["loss"] != "linear":
        found.append(
            Diagnostic(
                "D_PRIORS_ACTIVE",
                NOTE,
                where={"prior": "robust_loss", "loss": config.optimization["loss"]},
                measured=config.optimization["f_scale"],
                threshold="none",
                threshold_source="ledger C6",
            )
        )

    if declared is not None:
        silenced = {
            "smoothing": declared.smoothing["enabled"],
            "monotonic_penalty": declared.monotonic_penalty["enabled"],
            "low_field_weight": declared.optimization["low_field_weight"]["enabled"],
            "loss": declared.optimization["loss"],
        }
        found.append(
            Diagnostic(
                "D_PRIORS_DISABLED",
                NOTE,
                where={"switch": "--no-priors"},
                measured=silenced,
                threshold="none",
                threshold_source="FR-057",
            )
        )
    return found


# ------------------------------------------------------------------ collect

def interval_lower_bound(uncertainties) -> list[Diagnostic]:
    """FR-060. An interval that does not cover what made the residual structured.

    Research 002 section 3.2 measured the understatement on this sample: an
    independent resample gives 4.2 % against the 5 to 15 % the counterfactual
    of research 001 section 4.8 puts the same parameters at. The interval is
    not wrong, it is incomplete, and a reader who is not told will read it as
    the whole uncertainty.
    """
    return [
        Diagnostic(
            "D_INTERVAL_LOWER_BOUND",
            WARNING,
            where={"T_K": entry.T_K},
            measured=entry.block_length,
            threshold=None,
            threshold_source="FR-060",
        )
        for entry in (uncertainties or ())
        if entry.lower_bound
    ]


def spectrum_reading(spectra) -> list[Diagnostic]:
    """What the spectrum could and could not settle. FR-069, FR-071, FR-073.

    One entry per carrier type where a type is the thing at fault, because
    after separation the hole and the electron problems succeed and fail
    independently: a clean hole branch beside an unresolved electron one is a
    real and reportable state.
    """
    found: list[Diagnostic] = []
    for entry in (spectra or ()):
        extension = entry.extension
        if extension.max_relative_residual > 10.0 * max(entry.noise):
            found.append(
                Diagnostic(
                    "D_SPECTRUM_EXTENSION_UNDERFIT",
                    WARNING,
                    where={"T_K": entry.T_K, "terms": extension.n_terms},
                    measured=extension.max_relative_residual,
                    threshold=10.0 * max(entry.noise),
                    threshold_source="AC-021",
                )
            )
        if extension.at_bound:
            found.append(
                Diagnostic(
                    "D_SPECTRUM_EXTENSION_SATURATED",
                    WARNING,
                    where={"T_K": entry.T_K},
                    measured=extension.n_terms,
                    threshold=None,
                    threshold_source="FR-069",
                )
            )
        if extension.n_starts_agreeing * 2 < extension.n_starts:
            found.append(
                Diagnostic(
                    "D_SPECTRUM_EXTENSION_MULTIMODAL",
                    NOTE,
                    where={"T_K": entry.T_K},
                    measured=extension.n_starts_agreeing,
                    threshold=extension.n_starts,
                    threshold_source="FR-068",
                )
            )
        tolerance = float(entry.roundtrip_tolerance)
        for channel, measured in (
            ("rhoxx", entry.roundtrip_rhoxx),
            ("rhoxy", entry.roundtrip_rhoxy),
        ):
            if measured == measured and measured > tolerance:   # NaN-safe
                found.append(
                    Diagnostic(
                        "D_SPECTRUM_ROUNDTRIP",
                        WARNING,
                        where={"T_K": entry.T_K, "channel": channel},
                        measured=measured,
                        threshold=tolerance,
                        threshold_source="AC-025",
                    )
                )

        if not extension.constrained:
            found.append(
                Diagnostic(
                    "D_SPECTRUM_UNCONSTRAINED",
                    WARNING,
                    where={"T_K": entry.T_K},
                    measured=False,
                    threshold=True,
                    threshold_source="NR-011",
                )
            )

        for branch in entry.branches:
            where = {"T_K": entry.T_K, "kind": branch.kind}
            if branch.negative_fraction > 0.0:
                found.append(
                    Diagnostic(
                        "D_SPECTRUM_NEGATIVE_PART",
                        WARNING,
                        where=where,
                        measured=branch.negative_fraction,
                        threshold=0.0,
                        threshold_source="AC-024",
                    )
                )
            if not branch.noise_reached:
                found.append(
                    Diagnostic(
                        "D_SPECTRUM_NOISE_UNREACHED",
                        WARNING,
                        where=where,
                        measured=min(step.residual_norm for step in branch.steps),
                        threshold=entry.target_residual_norm,
                        threshold_source="AC-018",
                    )
                )
            if len(branch.plateaus) == 0:
                found.append(
                    Diagnostic(
                        "D_SPECTRUM_UNRESOLVED",
                        WARNING,
                        where=where,
                        measured=0,
                        threshold=1,
                        threshold_source="AC-020",
                    )
                )
            elif len(branch.plateaus) > 1:
                found.append(
                    Diagnostic(
                        "D_SPECTRUM_AMBIGUOUS",
                        WARNING,
                        where=dict(
                            where,
                            counts="/".join(str(pair[0]) for pair in branch.plateaus),
                        ),
                        measured=len(branch.plateaus),
                        threshold=1,
                        threshold_source="AC-020",
                    )
                )
    return found


def collect(
    result: RunResult,
    dataset: Dataset,
    declared: ResolvedConfig | None = None,
    uncertainties=(),
    spectra=(),
) -> list[Diagnostic]:
    """Every diagnostic, in the order a reader should meet them. FR-042.

    Conditioning first: it is the one line that says whether the data
    determined the answer at all.
    """
    return [
        *conditioning(result),
        *non_unique(result),
        *low_mu_b(result, dataset),
        *residual_structure(result, dataset),
        *fit_quality(result),
        *at_bound(result),
        *jumps_and_swaps(result),
        *field_window(result, dataset),
        *bound_overrides(result),
        *priors(result.config, declared),
        *intake(dataset),
        *parity_violation(dataset, result.config),
        *harmonic_ladder(result),
        *interval_lower_bound(uncertainties),
        *spectrum_reading(spectra),
    ]
