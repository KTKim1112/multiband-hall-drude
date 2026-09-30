"""What a job does: the analysis, and the precise check. FR-101, FR-102, FR-104.

Both are thin. The analysis is `mbfit.workflow.analyse` with the job's progress
and stop wired in, followed by the same two writers the command line calls, so
the files a reader downloads are the files the command line would have written
(FR-104). The precise check is the resampling of feature 002 on the carriers
fit mode chose at one temperature.
"""

from __future__ import annotations

import copy
import json
import math
import pathlib
import time
from typing import Any

from mbfit import spectrum as spectrum_module
from mbfit import uncertainty, workflow, workflow_report
from mbfit.config import resolve, temperature_range
from mbfit.core.errors import MbfitError
from mbfit.dataio import Dataset
from mbfit.fitting import fit_dataset
from mbfit.messages import REPORT_TEXT

from . import tables
from .errors import AppError
from .jobs import SUCCEEDED, Job, Stop

#: FR-102. The preliminary fit supplies the spectrum's noise level, and a
#: reader of the page declares no carriers. Two of each sign, starts a decade
#: apart, bounds wide enough to hold any metal or semimetal. Research 005
#: section 2 measured this generic set against the carefully seeded one used
#: throughout research 004, on all twelve reference sweeps: the same carrier
#: bound at every temperature and the same noise level to within 3 %.
PRELIMINARY_CARRIERS = (
    {"name": "h1", "kind": "hole", "density": {"init": 1e20, "min": 1e15, "max": 1e24},
     "mobility": {"init": 1e4, "min": 1.0, "max": 1e6}},
    {"name": "h2", "kind": "hole", "density": {"init": 1e21, "min": 1e15, "max": 1e24},
     "mobility": {"init": 1e3, "min": 1.0, "max": 1e6}},
    {"name": "e1", "kind": "electron", "density": {"init": 1e20, "min": 1e15, "max": 1e24},
     "mobility": {"init": 1e4, "min": 1.0, "max": 1e6}},
    {"name": "e2", "kind": "electron", "density": {"init": 1e21, "min": 1e15, "max": 1e24},
     "mobility": {"init": 1e3, "min": 1.0, "max": 1e6}},
)

COMBINED = "combined.csv"

#: FR-025. Second-order curvature needs three points in a segment; with two
#: there is nothing for a curvature to be formed from.
SMOOTHING_NEEDS = 3


def document_for(supplied: dict | None, mode: str, symmetrize_rhoxx: bool,
                 antisymmetrize_rhoxy: bool) -> tuple[dict, list[dict]]:
    """The configuration document the analysis runs on, and the model it names."""
    if supplied:
        document = copy.deepcopy(supplied)
    else:
        document = {"schema_version": "1.0",
                    "carriers": copy.deepcopy(list(PRELIMINARY_CARRIERS))}
    document["columns"] = dict(tables.COLUMNS)
    preprocess = document.setdefault("preprocess", {})
    # FR-100. Off unless the reader turned it on, here or in their document.
    if symmetrize_rhoxx:
        preprocess["symmetrize_rhoxx"] = True
    if antisymmetrize_rhoxy:
        preprocess["antisymmetrize_rhoxy"] = True
    document.setdefault("spectrum", {})["enabled"] = True
    document.setdefault("workflow", {})["count"] = mode
    document.setdefault("output", {})["make_plots"] = False
    resolve(document)          # a bad document fails the request, not the job

    preliminary = [
        {"name": c["name"], "kind": c["kind"],
         "density_cm3": c["density"]["init"], "mobility_cm2Vs": c["mobility"]["init"]}
        for c in document["carriers"]
    ]
    return document, preliminary


def analysis(combined: tables.Combined, document: dict, mode: str,
             workdir: pathlib.Path):
    """The work of an analysis job."""

    def work(job: Job) -> dict:
        workdir.mkdir(parents=True, exist_ok=True)
        path = workdir / COMBINED
        path.write_text(combined.text, encoding="utf-8")
        hooks = workflow.Hooks(progress=job.report, stop=job.stopped)
        started = time.monotonic()
        try:
            result = workflow.analyse(path, document, mode=mode, hooks=hooks)
        except workflow.Cancelled as stopped:
            # FR-098. What finished is kept and shown.
            partial = None
            if stopped.outcomes:
                partial = workflow_report.payload(workflow.WorkflowResult(
                    mode=mode, outcomes=stopped.outcomes,
                    seconds=time.monotonic() - started, dataset=stopped.dataset,
                    hall_polarity=stopped.hall_polarity))
            raise Stop(partial) from None

        workflow_report.write_tables(result, workdir)
        workflow_report.write_page(result, workdir, REPORT_TEXT)
        add_model_to_combined(path, result)
        job.context.update(analysis=result, workdir=workdir, document=document)
        answer = workflow_report.payload(result)
        # FR-005. Rows the page discarded while combining the uploads. The
        # library counts what it drops from the table it is handed; these were
        # never in it, so this is the only place the reader can be told.
        answer["dropped_before_fit"] = int(combined.dropped)
        return answer

    return work


def add_model_to_combined(path: pathlib.Path, result) -> None:
    """Put the fitted curve beside the measurement in the table that travels.

    `combined.csv` is the reader's own sweeps gathered into one table, and
    handing those back unchanged is of no use to the person who supplied them.
    The model belongs next to them, at the same field and the same temperature,
    so the two can be subtracted or plotted without stitching files together.

    The four declared columns are left exactly as they were and the rest is
    appended, because this file is also what `--data` reads to reproduce the
    run: `dataio.read_table` takes those four by name and never looks at the
    others, so the model rides along without the reproduction noticing.

    The added columns are the ones the command line already writes per
    temperature, and mean the same. Two of them are written only when they
    would not repeat the row they sit on: `measured` is the channel as the fit
    saw it, which is the raw column itself unless preprocessing changed it, and
    `in_fit_window` is true of every row unless a field range was declared.
    `residual` is measured minus fitted, taken from the fit's own view so that
    it stays the residual the verdict was reached on -- which is why `measured`
    appears exactly where the subtraction would otherwise look wrong.
    """
    import numpy as np
    import pandas as pd

    from mbfit.workflow import _model_of

    groups = {float(g.T_K): g for g in getattr(result, "dataset", None).groups} \
        if getattr(result, "dataset", None) is not None else {}
    if not groups:
        return
    polarity = float(getattr(result, "hall_polarity", 1.0))

    #: (T, B) -> what the fit saw, what the model says, and whether it counted.
    at: dict[tuple[float, float], tuple[float, float, float, float, bool]] = {}
    for item in result.outcomes:
        group = groups.get(float(item.T_K))
        if group is None or not item.carriers:
            continue
        fit_xx, fit_xy = _model_of(group, list(item.carriers), polarity)
        window = np.asarray(getattr(group, "in_fit_window",
                                    np.ones(np.asarray(group.B_T).size, dtype=bool)))
        for index, B in enumerate(np.asarray(group.B_T)):
            at[(float(item.T_K), float(B))] = (
                float(np.asarray(group.rhoxx_uohmcm)[index]),
                float(np.asarray(group.rhoxy_uohmcm)[index]),
                float(np.asarray(fit_xx)[index]),
                float(np.asarray(fit_xy)[index]),
                bool(window[index]),
            )

    table = pd.read_csv(path)
    keys = list(zip(pd.to_numeric(table[tables.COLUMNS["T"]], errors="coerce"),
                    pd.to_numeric(table[tables.COLUMNS["B"]], errors="coerce")))
    # A sweep the procedure never answered for -- a stop, or a count that fit
    # nothing -- leaves its rows empty rather than dropping them: the table is
    # the reader's own data and stays whole.
    blank = (math.nan,) * 4 + (True,)
    found = [at.get((float(T), float(B)), blank) for T, B in keys]
    answered = [(float(T), float(B)) in at for T, B in keys]

    raw_xx = pd.to_numeric(table[tables.COLUMNS["rhoxx"]], errors="coerce")
    raw_xy = pd.to_numeric(table[tables.COLUMNS["rhoxy"]], errors="coerce")

    # Two of these columns would repeat what is already in the table, and a
    # column that repeats its neighbour is one more thing to read and mistrust.
    # Each is written only where it says something the row does not already
    # say: `measured` where preprocessing gave the fit different numbers to
    # look at -- symmetrising, or the Hall scale of FR-007 -- and the window
    # where a declared field range left some rows out of the fit.
    preprocessed = any(
        here and (row[0] != float(xx) or row[1] != float(xy))
        for here, row, xx, xy in zip(answered, found, raw_xx, raw_xy))
    windowed = any(here and not row[4] for here, row in zip(answered, found))

    if windowed:
        table["in_fit_window"] = [row[4] for row in found]
    if preprocessed:
        table["rhoxx_measured(microohm_cm)"] = [row[0] for row in found]
    table["rhoxx_fitted(microohm_cm)"] = [row[2] for row in found]
    table["rhoxx_residual(microohm_cm)"] = [row[0] - row[2] for row in found]
    if preprocessed:
        table["rhoxy_measured(microohm_cm)"] = [row[1] for row in found]
    table["rhoxy_fitted(microohm_cm)"] = [row[3] for row in found]
    table["rhoxy_residual(microohm_cm)"] = [row[1] - row[3] for row in found]
    table.to_csv(path, index=False)


#: The document written beside a confirmed answer, and read back by a reader
#: who wants the same answer from the command line a year later (NR-013).
CONFIRMED_CONFIG = "config.json"


def _reaches(low: float, high: float, key: str) -> bool:
    """Does the closed band `low` to `high` hold any temperature this key names?"""
    try:
        at_low, at_high = temperature_range(str(key), "workflow.fixed_counts")
    except MbfitError:
        return False           # `resolve` reports a bad key, and names it
    return at_low <= high + 1e-6 and at_high >= low - 1e-6


def _carried_forward(work: dict, fixed_counts: dict,
                     smooth_band: list) -> tuple[dict, list]:
    """FR-112. The adjustments stand where they reach and the document keeps
    the rest of what it declared.

    Replacing the two settings outright loses whatever the reader's own
    configuration pinned or coupled for a temperature they never adjusted. The
    analysis then ran under that setting and the confirmation did not, so the
    confirmed answer could differ from the one being confirmed at a sweep
    nobody touched -- the one thing a confirmation must not do.

    Nothing has to choose between two pinned counts here: `workflow.count_for`
    gives a sweep the narrowest range that covers it, and the page pins one
    temperature at a time, so an adjustment already beats a band around it. A
    coupling is different -- it is refused unless its sweeps share a count --
    so a declared band that an adjustment lands inside is dropped, which is the
    rule the page itself follows: a band half adjusted is not one series.
    """
    carried = dict(work.get("fixed_counts") or {})
    carried.update(fixed_counts)

    asked = {str(band.get("range")) for band in smooth_band}
    kept = []
    for band in work.get("smooth_band") or []:
        if str(band.get("range")) in asked:
            continue           # the reader asked for this band again, their way
        try:
            low, high = temperature_range(str(band.get("range", "")),
                                          "workflow.smooth_band")
        except MbfitError:
            kept.append(band)  # malformed: `resolve` refuses it, and says why
            continue
        if any(_reaches(low, high, at) for at in fixed_counts):
            continue
        kept.append(band)
    return carried, kept + list(smooth_band)


def document_for_confirm(parent: Job, fixed_counts: dict, smooth_band: list) -> dict:
    """The analysis document, plus the settings the adjustments amount to.

    Settings, not the numbers already on the page. Re-running under them is
    what makes the tables honest: a table of combinations tried, assembled
    from an adjusted answer, would describe the search that produced the answer
    being overridden. It is also what makes FR-104 true rather than argued.
    """
    if parent.kind != "analysis" or parent.state != SUCCEEDED or "document" not in parent.context:
        raise AppError("E_JOB_NOT_FINISHED", job_id=parent.job_id)
    if not fixed_counts and not smooth_band:
        raise AppError("E_CONFIRM_EMPTY")
    document = copy.deepcopy(parent.context["document"])
    work = document.setdefault("workflow", {})
    work["fixed_counts"], work["smooth_band"] = _carried_forward(
        work, fixed_counts, smooth_band)
    resolve(document)          # a bad adjustment fails the request, not the job
    return document


def confirm(parent: Job, document: dict, workdir: pathlib.Path):
    """FR-112. The procedure, run again under the settings the reader assembled.

    Its own directory, so that the answer the procedure reached stays
    downloadable beside it: confirming adds an answer, it does not erase one.
    """
    mode = str(document.get("workflow", {}).get("count", "data"))
    source = pathlib.Path(parent.context["workdir"]) / COMBINED

    def work(job: Job) -> dict:
        workdir.mkdir(parents=True, exist_ok=True)
        path = workdir / COMBINED
        path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        hooks = workflow.Hooks(progress=job.report, stop=job.stopped)
        try:
            result = workflow.analyse(path, document, mode=mode, hooks=hooks)
        except workflow.Cancelled:
            # A confirmed answer covering some of the temperatures is not a
            # confirmed answer, so a stop keeps none of it.
            raise Stop(None) from None
        workflow_report.write_tables(result, workdir)
        workflow_report.write_page(result, workdir, REPORT_TEXT)
        add_model_to_combined(path, result)
        (workdir / CONFIRMED_CONFIG).write_text(
            json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
        job.context.update(analysis=result, workdir=workdir, document=document)
        return workflow_report.payload(result)

    return work


def outcome_for_precise(parent: Job, T_K: float):
    """The fit-mode outcome at one temperature, or the code that says why not."""
    result = parent.context.get("analysis")
    if result is None:
        raise AppError("E_JOB_NOT_FINISHED", job_id=parent.job_id)
    match = [item for item in result.outcomes if math.isclose(item.T_K, T_K, abs_tol=1e-6)]
    if not match:
        raise AppError("E_PRECISE_UNKNOWN_TEMPERATURE", T_K=T_K)
    outcome = match[0]
    # Both count rules end in a fit, so either can be resampled; a temperature
    # where the peaks rule found nothing to fit cannot.
    if not outcome.carriers:
        raise AppError("E_PRECISE_NO_ANSWER", T_K=outcome.T_K)
    group = next(g for g in result.dataset.groups if math.isclose(g.T_K, outcome.T_K, abs_tol=1e-6))
    return outcome, group


def outcome_for_recount(parent: Job, T_K: float):
    """The outcome and sweep at one temperature of a finished analysis. FR-109.

    Unlike the precise check this does not require that the temperature already
    has an answer: a temperature where nothing was selected is exactly one a
    reader may want to refit at a count of their own.
    """
    result = parent.context.get("analysis")
    if result is None:
        raise AppError("E_JOB_NOT_FINISHED", job_id=parent.job_id)
    match = [item for item in result.outcomes if math.isclose(item.T_K, T_K, abs_tol=1e-6)]
    if not match:
        raise AppError("E_PRECISE_UNKNOWN_TEMPERATURE", T_K=T_K)
    group = next(g for g in result.dataset.groups
                 if math.isclose(g.T_K, match[0].T_K, abs_tol=1e-6))
    return match[0], group


def _finite(value) -> float | None:
    """A number for the page, or nothing where the quantity does not apply."""
    value = float(value)
    return value if math.isfinite(value) else None


def recount(parent: Job, temperatures, n_hole: int, n_electron: int):
    """A sweep, or a band of them, refitted at a count the reader chose. FR-109.

    A band is the case that matters. FR-090's reason is that `n(T)` cannot be
    plotted across a model that changes underneath it, and one carrier set over
    one temperature settles nothing about a series; a single sweep is the band
    of length one.

    `workflow._refit_at` is the routine the command line already uses to hold a
    count fixed, so what the page answers here and what `workflow.fixed_counts`
    answers there is the same answer, including what the choice cost.

    A finished analysis does not keep the spectrum entries -- they are local to
    the loop that built them -- so each entry is rebuilt from its own sweep
    alone. That is one declared fit per temperature asked for, not one over the
    whole table.
    """
    wanted = [outcome_for_recount(parent, T_K) for T_K in temperatures]
    document = parent.context["document"]
    path = pathlib.Path(parent.context["workdir"]) / COMBINED

    def work(job: Job) -> dict:
        base = json.loads(json.dumps(document))
        base.setdefault("spectrum", {})["enabled"] = True
        config = resolve(base)
        settings = dict(config.workflow)
        equivalence = float(config.acceptance["cost_equivalence"])
        polarity = float(config.model["hall_polarity"])
        hooks = workflow.Hooks(progress=job.report, stop=job.stopped)

        started = time.monotonic()
        total = len(wanted)
        refitted = []
        unheld: list[float] = []
        for index, (outcome, group) in enumerate(wanted):
            job.report({"stage": "spectrum", "T_K": float(outcome.T_K),
                        "index": index, "total": total})
            one = Dataset(groups=(group,), n_records_dropped=0)
            declared = fit_dataset(one, config)
            entry = spectrum_module.for_temperature(declared.fits[0], group, config)
            job.report({"stage": "fixed", "T_K": float(outcome.T_K), "index": index,
                        "total": total, "holes": n_hole, "electrons": n_electron})
            try:
                held = workflow._refit_at(path, base, entry, settings, equivalence,
                                          int(n_hole), int(n_electron), outcome, hooks)
            except workflow.Cancelled:
                # A band half held to one count and half to another is not a
                # series either, so a stop keeps none of it.
                raise Stop(None) from None
            if held is None:
                # FR-109. The count would not fit at this sweep inside the
                # budget. The procedure's own answer stands here, and the page
                # is told which sweeps those were: a band silently part pinned
                # and part not is the mixed series FR-090 exists to prevent,
                # and it would be reported as a refit that had succeeded.
                unheld.append(float(outcome.T_K))
                held = outcome
            refitted.append(workflow.with_fit_quality(held, group, polarity))

        result = workflow.WorkflowResult(
            mode=refitted[0].mode, outcomes=tuple(refitted),
            seconds=time.monotonic() - started,
            dataset=Dataset(groups=tuple(group for _, group in wanted),
                            n_records_dropped=0),
            hall_polarity=polarity)
        answer = workflow_report.payload(result)

        # FR-025. How far the band is from a smooth series is free to compute
        # and worth knowing whether or not anyone asks for it to be forced.
        answer["roughness"] = _finite(workflow.roughness_of(refitted))
        answer["smoothing"] = None
        # FR-109. The sweeps the pin could not be applied to, named rather than
        # folded into the answer as though it had been.
        answer["unheld"] = unheld

        # FR-109, amended. The coupling is asked for separately, of this
        # answer. It was once the tail of this same job, and a coupling over a
        # long band takes far longer than the refits it follows, so asking for
        # one withheld refits that were already complete -- a page that did
        # nothing for hours. What a later coupling needs is kept here; none of
        # it is ever serialised (`app/jobs.py`).
        job.context.update(band=refitted, groups=[group for _, group in wanted],
                           document=base, settings=settings,
                           equivalence=equivalence, polarity=polarity)
        return answer

    return work


def band_for_smoothing(parent: Job):
    """Refuse a coupling before it starts, rather than inside the job. FR-109."""
    if (parent.kind != "recount" or parent.state != SUCCEEDED
            or "band" not in parent.context):
        raise AppError("E_SMOOTH_NO_BAND", job_id=parent.job_id)
    band = parent.context["band"]
    if len(band) < SMOOTHING_NEEDS:
        raise AppError("E_SMOOTHING_TOO_FEW", given=len(band),
                       needed=SMOOTHING_NEEDS)
    counts = sorted({f"{item.n_hole}h+{item.n_electron}e" for item in band})
    if len(counts) != 1:
        # A coupling across sweeps that do not share a carrier set has nothing
        # to couple. `smooth_band` refuses it too, but with a bare exception
        # that would reach the reader as an internal fault.
        raise AppError("E_BAND_COUNTS_DIFFER", counts=counts)
    return band


def smooth(parent: Job, strength: str):
    """The coupling of FR-027 over a band already held to one count. FR-109.

    Its own job, because it is the slow half and because a stop should mean one
    thing: stopping this leaves the refit it was asked of standing.
    """
    refitted = band_for_smoothing(parent)
    groups = parent.context["groups"]
    base = parent.context["document"]
    settings = parent.context["settings"]
    equivalence = parent.context["equivalence"]
    polarity = parent.context["polarity"]

    def work(job: Job) -> dict:
        hooks = workflow.Hooks(progress=job.report, stop=job.stopped)
        started = time.monotonic()
        try:
            coupled, lam = workflow.smooth_band(
                base, refitted, groups, settings, equivalence, strength, hooks)
        except workflow.Cancelled:
            # Nothing is kept: a band half coupled is not a smooth series. The
            # refit it was asked of is untouched, in its own job.
            raise Stop(None) from None
        except MbfitError as error:
            if error.code == "E_FIT_NO_START" and error.detail.get("n_expired"):
                raise AppError("E_BUDGET_EXPIRED",
                               seconds=round(time.monotonic() - started, 1),
                               expired=error.detail["n_expired"]) from None
            raise
        coupled = [workflow.with_fit_quality(item, group, polarity)
                   for item, group in zip(coupled, groups)]
        together = workflow.WorkflowResult(
            mode=coupled[0].mode, outcomes=tuple(coupled),
            seconds=time.monotonic() - started,
            dataset=Dataset(groups=tuple(groups), n_records_dropped=0),
            hall_polarity=polarity)
        job.context.update(band=coupled, groups=groups, document=base,
                           settings=settings, equivalence=equivalence,
                           polarity=polarity)
        return {
            "strength": strength,
            "lambda": lam,
            "roughness": _finite(workflow.roughness_of(coupled)),
            "temperatures": workflow_report.payload(together)["temperatures"],
        }

    return work


def precise(parent: Job, T_K: float):
    """The work of a precise-check job. FR-101."""
    outcome, group = outcome_for_precise(parent, T_K)
    document = json.loads(json.dumps(parent.context["document"]))

    def work(job: Job) -> dict:
        document["carriers"] = workflow._carrier_document(list(outcome.carriers), None)
        document["spectrum"] = {"enabled": False}
        document.setdefault("uncertainty", {})["enabled"] = True
        config = resolve(document)
        dataset = Dataset(groups=(group,), n_records_dropped=0)
        run = fit_dataset(dataset, config)
        structured = outcome.T_K in uncertainty.structured_temperatures(run, dataset)
        draws = int(config.uncertainty["resamples"])
        job.report({"stage": "resample", "T_K": outcome.T_K, "done": 0, "total": draws})

        def progress(done: int, total: int) -> None:
            job.report({"stage": "resample", "T_K": outcome.T_K, "done": done, "total": total})

        try:
            found = uncertainty.resample_temperature(
                run.fits[0], group, config, structured, progress=progress, stop=job.stopped)
        except uncertainty.Stopped:
            raise Stop(None) from None

        return {
            "T_K": found.T_K,
            "resamples": found.resamples,
            "block_length": found.block_length,
            "seed": found.seed,
            "lower_bound": found.lower_bound,
            "parameters": [_row(item) for item in found.parameters],
            "derived": [_row(item) for item in found.derived],
        }

    return work


def _row(interval) -> dict[str, Any]:
    row = interval.as_row()
    return {key: (value if not isinstance(value, float) or math.isfinite(value) else None)
            for key, value in row.items()}
