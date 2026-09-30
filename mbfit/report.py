"""Writing the result out. FR-037 to FR-042, FR-055.

The second of the two places `pandas` is allowed. Everything the program
knows leaves through here, in formats that open in Origin, Igor, Excel and
whatever else the reader already uses.

Two of these files matter more than the rest. `resolved_config.json` is the
run: fed back in, it reproduces every number, which is what makes a result
citable a year later. And `diagnostics.csv` is the evidence against trusting
the parameters, which is why the quickstart says to read it first.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import numpy as np
import pandas as pd

from .config import ResolvedConfig
from .core import harmonics
from .core.canonical import canonical_permutation
from .core.drude import conductivity_from_resistivity
from .core.units import resistivity_to_si
from .dataio import Dataset
from .diagnostics import Diagnostic
from . import spectrum as spectrum_module
from .fitting import RunResult, model_resistivity, signs


def _temperature_tag(T_K: float) -> str:
    return f"{T_K:g}K"


def write_resolved_config(result: RunResult, out: pathlib.Path) -> pathlib.Path:
    """FR-037. Every value in force, including the seed and every default."""
    document = result.config.as_document()
    document["_run"] = {
        "strategy": result.strategy,
        "seed": result.seed,
        "temperatures_K": list(result.temperatures),
        "global_condition_number": result.global_condition_number,
    }
    path = out / "resolved_config.json"
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_per_temperature(result: RunResult, dataset: Dataset, out: pathlib.Path):
    """FR-038. Measured, fitted and residual, in both spaces, every record.

    Every record, not only the admitted ones: FR-050 keeps the excluded region
    visible, because it is the evidence for whatever motivated excluding it.
    """
    polarity = float(result.config.model["hall_polarity"])
    written = []
    for fit, group in zip(result.fits, dataset.groups):
        sign = signs(fit.specs)
        model_xx, model_xy = model_resistivity(group.B_T, fit.params, sign, polarity)

        measured_sigma = conductivity_from_resistivity(
            resistivity_to_si(group.rhoxx_uohmcm), resistivity_to_si(group.rhoxy_uohmcm), polarity
        )
        model_sigma = conductivity_from_resistivity(
            resistivity_to_si(model_xx), resistivity_to_si(model_xy), polarity
        )

        frame = pd.DataFrame(
            {
                "B(T)": group.B_T,
                "in_fit_window": group.in_fit_window,
                "rhoxx_measured(microohm_cm)": group.rhoxx_uohmcm,
                "rhoxx_fitted(microohm_cm)": model_xx,
                "rhoxx_residual(microohm_cm)": group.rhoxx_uohmcm - model_xx,
                "rhoxy_measured(microohm_cm)": group.rhoxy_uohmcm,
                "rhoxy_fitted(microohm_cm)": model_xy,
                "rhoxy_residual(microohm_cm)": group.rhoxy_uohmcm - model_xy,
                "sigmaxx_measured(S_per_m)": measured_sigma[0],
                "sigmaxx_fitted(S_per_m)": model_sigma[0],
                "sigmaxx_residual(S_per_m)": measured_sigma[0] - model_sigma[0],
                "sigmaxy_measured(S_per_m)": measured_sigma[1],
                "sigmaxy_fitted(S_per_m)": model_sigma[1],
                "sigmaxy_residual(S_per_m)": measured_sigma[1] - model_sigma[1],
            }
        )
        path = out / f"{_temperature_tag(fit.T_K)}_fit.csv"
        frame.to_csv(path, index=False)
        written.append(path)
    return written


def write_parameters(result: RunResult, out: pathlib.Path) -> pathlib.Path:
    """FR-039, in both the declared order and the canonical one.

    Both, because PM-003 says the declared order carries no information while
    the reader still asked for those names, and because a change of canonical
    order between temperatures is what FR-047 reports.
    """
    rows = []
    for fit in result.fits:
        row: dict[str, Any] = {"T(K)": fit.T_K}
        for index, spec in enumerate(fit.specs):
            row[f"{spec.name}_density(cm^-3)"] = fit.params[2 * index]
            row[f"{spec.name}_mobility(cm^2_Vs)"] = fit.params[2 * index + 1]
        for index, spec in enumerate(fit.specs):
            row[f"canonical{index + 1}_{spec.kind}_density(cm^-3)"] = fit.params_canonical[2 * index]
            row[f"canonical{index + 1}_{spec.kind}_mobility(cm^2_Vs)"] = fit.params_canonical[
                2 * index + 1
            ]
        rows.append(row)
    path = out / "fit_parameters_vs_T.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_metrics(result: RunResult, out: pathlib.Path) -> pathlib.Path:
    """FR-040 and FR-051, with the conditioning of FR-055 beside them."""
    rows = []
    for fit in result.fits:
        rows.append(
            {
                "T(K)": fit.T_K,
                "R2_rhoxx": fit.r2_rhoxx,
                "R2_rhoxy": fit.r2_rhoxy,
                "RMSE_rhoxx(microohm_cm)": fit.rmse_rhoxx,
                "RMSE_rhoxy(microohm_cm)": fit.rmse_rhoxy,
                "R2_rhoxx_outside_window": fit.r2_outside,
                "RMSE_rhoxx_outside_window(microohm_cm)": fit.rmse_outside,
                "condition_number": fit.condition_number,
                "smallest_singular_value": float(fit.singular_values[-1]),
                "largest_singular_value": float(fit.singular_values[0]),
                "channel_scale_rhoxx": fit.channel_scales[0],
                "channel_scale_rhoxy": fit.channel_scales[1],
                "seed": fit.seed,
            }
        )
    path = out / "fit_metrics_vs_T.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_harmonics(result: RunResult, out: pathlib.Path) -> pathlib.Path:
    """FR-063, with the three conditions kept apart. Research 002 section 4.

    The diagnostic fires only when all three hold. This file carries the near
    misses too, because a reader deciding whether to believe a four-carrier
    decomposition wants the ratios, not a verdict.
    """
    tolerance = float(result.config.discriminants["harmonic_tolerance"])
    rows = []
    for fit in result.fits:
        params = fit.params_canonical
        sign = signs(fit.specs)
        # The canonical order permutes carriers only within a sign group, so
        # `sign` and the carrier kinds are unchanged by it. The declared
        # *names* are not: canonical position `i` holds the carrier declared
        # at `permutation[i]`, and using `specs[i]` would label the channels
        # with whichever name happened to be declared in that slot.
        permutation = canonical_permutation(fit.params, sign)
        verdict = harmonics.verdict(params[0::2], params[1::2], sign, tolerance)
        row: dict[str, Any] = {
            "T(K)": fit.T_K,
            "single_sign": verdict["single_sign"],
            "consecutive_integers": verdict["consecutive_integers"],
            "falling_weights": verdict["falling_weights"],
            "is_ladder": verdict["is_ladder"],
            "failed": " ".join(verdict["failed"]),
            "harmonic_tolerance": tolerance,
        }
        for rank, index in enumerate(verdict["order"], start=1):
            spec = fit.specs[permutation[index]]
            row[f"channel{rank}_name"] = spec.name
            row[f"channel{rank}_kind"] = spec.kind
            row[f"channel{rank}_mobility(cm^2_Vs)"] = float(params[2 * index + 1])
            row[f"channel{rank}_ratio_to_fastest"] = float(verdict["ratios"][rank - 1])
            row[f"channel{rank}_nearest_harmonic"] = int(verdict["harmonics"][rank - 1])
        rows.append(row)
    path = out / "harmonics_vs_T.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_starts(result: RunResult, out: pathlib.Path):
    """FR-036. Every starting point, not only the one that won."""
    written = []
    for fit in result.fits:
        rows = []
        for start in fit.starts:
            row: dict[str, Any] = {
                "start_index": start.start_index,
                "cost": start.cost,
                "converged": start.converged,
            }
            for index, spec in enumerate(fit.specs):
                row[f"{spec.name}_density(cm^-3)"] = start.params[2 * index]
                row[f"{spec.name}_mobility(cm^2_Vs)"] = start.params[2 * index + 1]
            rows.append(row)
        path = out / f"multistart_{_temperature_tag(fit.T_K)}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        written.append(path)
    return written


def write_diagnostics(found: list[Diagnostic], out: pathlib.Path) -> pathlib.Path:
    """FR-042 and FR-048, one row each, threshold and provenance included."""
    frame = pd.DataFrame(
        [entry.as_row() for entry in found],
        columns=["code", "severity", "where", "measured", "threshold", "threshold_source"],
    )
    path = out / "diagnostics.csv"
    frame.to_csv(path, index=False)
    return path


def write_figures(result: RunResult, dataset: Dataset, out: pathlib.Path):
    """FR-041. Skipped, with nothing else affected, if plotting is off."""
    if not result.config.output["make_plots"]:
        return []

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dpi = int(result.config.output["plot_dpi"])
    polarity = float(result.config.model["hall_polarity"])
    written = []

    for fit, group in zip(result.fits, dataset.groups):
        sign = signs(fit.specs)
        model_xx, model_xy = model_resistivity(group.B_T, fit.params, sign, polarity)
        for channel, measured, modelled, label in (
            ("rhoxx", group.rhoxx_uohmcm, model_xx, r"$\rho_{xx}$ ($\mu\Omega$ cm)"),
            ("rhoxy", group.rhoxy_uohmcm, model_xy, r"$\rho_{xy}$ ($\mu\Omega$ cm)"),
        ):
            figure, axes = plt.subplots(figsize=(5.0, 3.6))
            admitted = group.in_fit_window
            axes.plot(group.B_T[admitted], measured[admitted], "o", ms=3, label="measured, fitted")
            if not np.all(admitted):
                axes.plot(
                    group.B_T[~admitted], measured[~admitted], "x", ms=4,
                    label="measured, outside the window",
                )
            axes.plot(group.B_T, modelled, "-", lw=1.5, label="model")
            axes.set_xlabel("B (T)")
            axes.set_ylabel(label)
            axes.set_title(f"{fit.T_K:g} K")
            axes.legend(fontsize=7)
            figure.tight_layout()
            path = out / f"{_temperature_tag(fit.T_K)}_{channel}.png"
            figure.savefig(path, dpi=dpi)
            plt.close(figure)
            written.append(path)

    if len(result.fits) > 1:
        figure, axes = plt.subplots(2, 1, figsize=(5.0, 6.0), sharex=True)
        temperatures = [fit.T_K for fit in result.fits]
        for index, spec in enumerate(result.fits[0].specs):
            axes[0].plot(
                temperatures,
                [fit.params_canonical[2 * index] for fit in result.fits],
                "o-", ms=3, label=f"canonical {index + 1} ({spec.kind})",
            )
            axes[1].plot(
                temperatures,
                [fit.params_canonical[2 * index + 1] for fit in result.fits],
                "o-", ms=3,
            )
        axes[0].set_ylabel(r"density (cm$^{-3}$)")
        axes[1].set_ylabel(r"mobility (cm$^2$/Vs)")
        axes[1].set_xlabel("T (K)")
        for panel in axes:
            panel.set_yscale("log")
        axes[0].legend(fontsize=7)
        figure.tight_layout()
        path = out / "parameters_vs_T.png"
        figure.savefig(path, dpi=dpi)
        plt.close(figure)
        written.append(path)

    return written


def write_uncertainty(uncertainties, out: pathlib.Path):
    """FR-058 and FR-060, one file per temperature."""
    written = []
    for entry in uncertainties:
        rows = []
        for interval in entry.parameters:
            row = interval.as_row()
            row["block_length"] = entry.block_length
            row["resamples"] = entry.resamples
            row["lower_bound_only"] = entry.lower_bound
            rows.append(row)
        path = out / f"uncertainty_{_temperature_tag(entry.T_K)}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        written.append(path)
    return written


def write_correlation(uncertainties, out: pathlib.Path):
    """FR-062. Research 002 section 3.3 measured this to be the stable part."""
    written = []
    for entry in uncertainties:
        frame = pd.DataFrame(entry.correlation, index=list(entry.names), columns=list(entry.names))
        path = out / f"correlation_{_temperature_tag(entry.T_K)}.csv"
        frame.to_csv(path, index=True, index_label="parameter")
        written.append(path)
    return written


def write_derived(uncertainties, out: pathlib.Path) -> pathlib.Path | None:
    """FR-061. The combinations, which are not among the parameters."""
    if not uncertainties:
        return None
    rows = []
    for entry in uncertainties:
        row: dict[str, Any] = {"T(K)": entry.T_K}
        for interval in entry.derived:
            row[interval.name] = interval.value
            row[f"{interval.name}_low"] = interval.low
            row[f"{interval.name}_high"] = interval.high
            row[f"{interval.name}_one_sigma"] = interval.sigma
        row["block_length"] = entry.block_length
        row["resamples"] = entry.resamples
        row["lower_bound_only"] = entry.lower_bound
        rows.append(row)
    path = out / "derived_vs_T.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_spectrum(spectra, out: pathlib.Path):
    """FR-068, FR-073, FR-074, FR-077 and FR-079, five files per temperature.

    The stability file is the one a reader should open, and the extension file
    is the one that keeps them honest: every peak the spectrum shows sits on
    mobilities the Lorentzian extension chose, so a reader has to be able to
    see those.
    """
    written = []
    for entry in spectra:
        tag = _temperature_tag(entry.T_K)

        frame = {"mobility(cm^2_Vs)": entry.branches[0].mu_grid_m2Vs * 1e4}
        for branch in entry.branches:
            frame[f"{branch.kind}_density(S_per_m)"] = branch.density
        pd.DataFrame(frame).to_csv(out / f"spectrum_{tag}.csv", index=False)
        written.append(out / f"spectrum_{tag}.csv")

        rows = []
        for branch in entry.branches:
            for carrier in spectrum_module.carriers_from(branch, entry.sigma_xx_zero):
                rows.append({
                    "kind": carrier["kind"],
                    "mobility(cm^2_Vs)": carrier["mobility_cm2Vs"],
                    "density(cm^-3)": carrier["density_cm3"],
                    "weight": carrier["weight"],
                    "alpha": branch.alpha,
                    "noise_reached": branch.noise_reached,
                })
        pd.DataFrame(rows).to_csv(out / f"spectrum_peaks_{tag}.csv", index=False)
        written.append(out / f"spectrum_peaks_{tag}.csv")

        rows = []
        for branch in entry.branches:
            for step in branch.steps:
                rows.append({
                    "kind": branch.kind,
                    "alpha": step.alpha,
                    "residual_norm": step.residual_norm,
                    "target_residual_norm": entry.target_residual_norm,
                    "roughness": step.roughness,
                    "n_peaks": step.n_peaks,
                    "selected": step.alpha == branch.alpha,
                })
        pd.DataFrame(rows).to_csv(out / f"spectrum_stability_{tag}.csv", index=False)
        written.append(out / f"spectrum_stability_{tag}.csv")

        extension = entry.extension
        pd.DataFrame({
            "mobility(cm^2_Vs)": extension.mobility_m2Vs * 1e4,
            "hole_weight": extension.weight_hole,
            "electron_weight": extension.weight_electron,
            "amplitude_X": extension.amplitude_X,
            "amplitude_Y": extension.amplitude_Y,
        }).to_csv(out / f"spectrum_extension_{tag}.csv", index=False)
        written.append(out / f"spectrum_extension_{tag}.csv")

        # FR-079. One row, two numbers, and the only check in the file set that
        # compares the spectrum with the measurement rather than with itself.
        pd.DataFrame([{
            "channel": "rhoxx",
            "max_relative_error": entry.roundtrip_rhoxx,
            "tolerance": entry.roundtrip_tolerance,
        }, {
            "channel": "rhoxy",
            "max_relative_error": entry.roundtrip_rhoxy,
            "tolerance": entry.roundtrip_tolerance,
        }]).to_csv(out / f"spectrum_roundtrip_{tag}.csv", index=False)
        written.append(out / f"spectrum_roundtrip_{tag}.csv")
    return written


def write_everything(
    result: RunResult,
    dataset: Dataset,
    found: list[Diagnostic],
    out_dir: str | pathlib.Path,
    uncertainties=(),
    spectra=(),
):
    """Every file of `data-model.md` section 4. Nothing outside `out_dir`."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = [
        write_resolved_config(result, out),
        write_parameters(result, out),
        write_metrics(result, out),
        write_harmonics(result, out),
        write_diagnostics(found, out),
    ]
    written += write_per_temperature(result, dataset, out)
    written += write_starts(result, out)
    written += write_spectrum(spectra, out)
    written += write_uncertainty(uncertainties, out)
    written += write_correlation(uncertainties, out)
    derived = write_derived(uncertainties, out)
    if derived is not None:
        written.append(derived)
    written += write_figures(result, dataset, out)
    return written
