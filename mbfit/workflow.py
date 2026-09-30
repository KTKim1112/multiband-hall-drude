"""The analysis as a procedure, and the two rules for the carrier count. Feature 004.

Features 001 to 003 supply a carrier fit, an uncertainty and a mobility
spectrum, and say nothing about how to use them together. This module is that
missing part. There is one procedure -- the spectrum bounds the problem, a
multiband Drude fit gives the answer -- and two rules for how many carriers
that fit has:

    data    the count the data requires and determines. The spectrum's peak
            count per sign is an upper limit; every combination up to it is
            fitted and one is selected by the gates of FR-085. The answer is
            the smallest set of conduction channels the sweep needs, with
            parameters it pins down.

    peaks   the count the spectrum's peaks give, held. This is the procedure
            of Liu et al., Supplemental Material section III: the peak values
            start a fit at that count, the fit is fed back into the Lorentzian
            extension, the spectrum is recomputed, and the loop repeats until
            the fitted densities and mobilities stop moving. The answer is the
            converged fit.

Both answers are fits. What differs is who decides the count: the data, or the
peak finder. Research 004 section 4.2 measures the consequence on this
project's sweeps -- the same `R^2`, and condition numbers of `1e2` against
`1e4` to `1e10` -- which is why `data` is the default and `peaks` is for a
reader with evidence from outside transport that the count is right.

Two implementation details here are not free choices; each was measured
costing an order of magnitude when it was made the obvious way. The mobility
window is taken per carrier *type* and never per peak (FR-082), and starting
points come from the spectrum's *distribution* and never from its peak list
(FR-083). Research 004 section 3 has the numbers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from .config import ResolvedConfig, resolve
from .core import lorentzian
from .core.canonical import split_parameters
from .core.constants import ELEMENTARY_CHARGE_C
from .core.errors import MbfitError
from .core.metrics import noise_second_difference, runs_test_z
from .core.units import mobility_from_si
from .dataio import Dataset, TemperatureGroup, load_dataset
from .fitting import FitStopped, RunResult, fit_dataset
from . import spectrum as spectrum_module

DATA_RULE = "data"
PEAK_RULE = "peaks"
MODES = (DATA_RULE, PEAK_RULE)

GRADES = (("A", 1e3), ("B", 1e4), ("C", 1e6))


class Cancelled(Exception):
    """The reader stopped the run. FR-098.

    Carries every temperature that finished before the stop, so a caller can
    still show them: an analysis stopped at the ninth temperature has eight
    answers worth reading.
    """

    def __init__(self, outcomes=(), dataset=None, hall_polarity: float = 1.0):
        super().__init__("cancelled")
        self.outcomes = tuple(outcomes)
        self.dataset = dataset
        self.hall_polarity = float(hall_polarity)


@dataclass
class Hooks:
    """How a caller watches a run and stops it. FR-097, FR-098.

    `progress` receives plain dictionaries -- a stage name and numbers, never a
    sentence (Article IV). `stop` is asked before every fit starts; a fit that
    is already running finishes or runs out of its budget first, which bounds
    the delay by AC-029.
    """

    progress: Any = None
    stop: Any = None

    def report(self, **event) -> None:
        if self.progress is not None:
            self.progress(event)

    def check(self) -> None:
        if self.stop is not None and self.stop():
            raise Cancelled()


_QUIET = Hooks()


def grade_of(condition_number: float) -> str:
    """How far the parameters of a fit can be trusted. AC-031.

    A grade and not a gate. Research 001 section 4.6 calibrated the threshold
    of `1000` between a case where every parameter returned to `0.1 %` and one
    where a density was wrong by `35 %`, so it separates trusting the digits
    from not trusting them -- not usable from useless. Gating on it rejected
    every combination between 30 and 60 K on this project's own data, where
    the answer fits to `R^2 > 0.998` and reproduces to `2e-8`.
    """
    if not np.isfinite(condition_number):
        return "D"
    for letter, ceiling in GRADES:
        if condition_number <= ceiling:
            return letter
    return "D"


# ------------------------------------------------------- what the spectrum gives

def window_of(entry, kind: str, factor: float) -> tuple[float, float]:
    """The mobility range this carrier type is allowed. FR-082, AC-030.

    Per carrier type, from the extreme peaks of that type, and never per peak.
    Binding carrier `i` to peak `i` assumes the count the spectrum proposed,
    which is the thing the search exists to vary: asking for two holes where
    the spectrum found three then takes the two fastest and puts the slow one's
    neighbourhood outside the bounds. Measured at 5 K, that raises the residual
    from `0.043` to `1.587`.
    """
    peaks = [
        item for item in spectrum_module.carriers_from(entry.branch(kind),
                                                       entry.sigma_xx_zero)
    ]
    if not peaks:
        return 30.0, 3.0e5
    mobilities = [item["mobility_cm2Vs"] for item in peaks]
    return min(mobilities) / factor, max(mobilities) * factor


def segment_seeds(mu_grid_cm2Vs, density, sigma_xx_zero: float,
                  total_density: float, wanted: int):
    """`wanted` starting points from the branch's distribution. FR-083.

    The branch is divided into `wanted` equal-weight segments and each
    segment's conductivity-weighted centre becomes one starting point. That is
    the best `wanted`-carrier summary of the same distribution and it is
    defined for any count, where the peak list is not.

    The peak list is the obvious choice and it fails: asking for fewer
    carriers than there are peaks takes the tallest and never seeds the rest,
    and the multi-start of feature 001 perturbs around its starting point
    rather than sampling the bounds, so it does not recover. Measured at 5 K,
    `0.427` against `0.043`.
    """
    mu = np.asarray(mu_grid_cm2Vs, dtype=float)
    weight = np.asarray(density, dtype=float)
    wanted = int(wanted)
    if wanted < 1 or weight.sum() <= 0.0 or total_density <= 0.0:
        return []

    share = weight / total_density
    running = np.cumsum(weight) / weight.sum()
    edges = [0]
    for step in range(1, wanted):
        edges.append(int(np.searchsorted(running, step / wanted)))
    edges.append(mu.size)

    out = []
    for low, high in zip(edges[:-1], edges[1:]):
        if high <= low:
            continue
        block = weight[low:high]
        if block.sum() <= 0.0:
            continue
        centre = float(np.exp((block * np.log(mu[low:high])).sum() / block.sum()))
        fraction = float(share[low:high].sum())
        # sigma_xx(0) * S = n q mu, in the units the boundary uses
        density_cm3 = (sigma_xx_zero * fraction
                       / (ELEMENTARY_CHARGE_C * centre * 1e-4)) * 1e-6
        out.append({"mobility_cm2Vs": centre, "density_cm3": density_cm3})
    return out[:wanted]


def spectrum_curves(entry) -> dict[str, Any]:
    """One sweep's mobility spectrum, as plain numbers a reader can be shown.

    Until now only the spectrum's conclusions left the procedure -- a count and
    a window. The curve is what those were read from, and it answers what a
    count cannot: whether a peak stands alone or is a shoulder of its
    neighbour, and how much of the distribution the window takes in.

    The vertical axis is the normalised weight the spectrum solves for, not a
    carrier density. The problem is posed with `X(0) = 1`, and turning a weight
    into a density is what `spectrum.carriers_from` does.
    """
    curves: dict[str, Any] = {}
    for kind in ("hole", "electron"):
        branch = entry.branch(kind)
        curves[kind] = {
            "mobility_cm2Vs": [float(v) for v in mobility_from_si(np.asarray(branch.mu_grid_m2Vs))],
            "weight": [float(v) for v in np.asarray(branch.density)],
            "peaks_cm2Vs": [float(mobility_from_si(peak["mu_m2Vs"])) for peak in branch.peaks],
        }
    return curves


def bounds_from(entry, factor: float) -> dict[str, Any]:
    """The whole of what the spectrum supplies to fit mode: a count and a range."""
    proposal = entry.proposal
    return {
        "count": {kind: int(proposal.get(kind, 0)) for kind in ("hole", "electron")},
        "window": {kind: window_of(entry, kind, factor)
                   for kind in ("hole", "electron")},
    }


# ------------------------------------------------------------------- candidates

@dataclass(frozen=True)
class Candidate:
    """One combination, fitted, and what it earned."""

    n_hole: int
    n_electron: int
    rmse_rhoxx: float
    rmse_rhoxy: float
    r2_rhoxx: float
    r2_rhoxy: float
    condition_number: float
    spread: float
    weakest_share: float
    at_bound: bool
    expired: bool
    n_starts: int
    seconds: float
    params: np.ndarray
    specs: tuple

    @property
    def label(self) -> str:
        return f"{self.n_hole}h+{self.n_electron}e"

    @property
    def n_carriers(self) -> int:
        return self.n_hole + self.n_electron


def spread_of(fit, equivalence: float) -> float:
    """How far apart the starts of indistinguishable cost ended up.

    Compared after canonicalisation, so that a relabelling is not counted as
    disagreement. Research 002 section 4.4 measured a naive comparison
    reporting a hundredfold non-uniqueness on a problem that has none.

    Fewer than two starts finished means the quantity was never measured, and
    an unmeasured spread is infinite, not zero. Returning zero here reported
    "nothing disagreed" about a fit nothing had been compared against, which is
    how a fit the clock cut down to one start could look perfectly reproducible.
    """
    from .core.canonical import canonical_permutation
    from .fitting import signs

    if len(fit.starts) < 2:
        return float("inf")
    sign = signs(fit.specs)
    best = min(start.cost for start in fit.starts)
    rivals = []
    for start in fit.starts:
        if start.cost <= best * (1.0 + equivalence) + 1e-300:
            order = canonical_permutation(start.params, sign)
            n, mu = split_parameters(start.params)
            rivals.append(np.concatenate([n[order], mu[order]]))
    if len(rivals) < 2:
        return 0.0
    block = np.vstack(rivals)
    return float(np.max(np.abs(block / block[0] - 1.0)))


def gates_of(candidate: Candidate, best_rmse: float, settings) -> dict[str, bool]:
    """The four tests with no defensible middle. FR-085.

    `fits` is first and is not traded against the rest. An early version of
    this ranked by how many tests failed and chose a combination whose residual
    was ten times worse because it failed the same number: a model that does
    not describe the data is not a candidate however well determined it is.

    `reproducible` is the spread alone. It used to also require that the fit
    had not run past its budget, which made the verdict depend on how fast the
    machine was: at 90 K `2h+2e` reached the same residual to six digits on two
    machines, took 17 s on one and 30 s on the other, and only the slower
    machine threw it away -- for `1h+2e`, whose residual is 2.6 times worse.
    The clock is not evidence about a model. Where it really cost the fit its
    starting points, `spread_of` reports that as an unmeasured spread and this
    gate fails on the measurement instead.
    """
    return {
        "fits": candidate.rmse_rhoxx <= best_rmse * float(settings["residual_factor"]),
        "reproducible": candidate.spread <= float(settings["spread_max"]),
        "earns": candidate.weakest_share >= float(settings["share_min"]),
        "free": not candidate.at_bound,
    }


def undetermined_better_of(candidates, rmse_rhoxx: float, settings) -> tuple[str, float]:
    """The best non-reproducible fit that beats `rmse_rhoxx` by the residual factor.

    FR-085. The scale for `fits` is taken from reproducible fits, so a
    reproducible combination can pass while an undetermined one describes the
    data far better. That must not pass silently: the label and the ratio are
    reported beside the verdict. Returns `("", nan)` when there is none.

    A combination with no fit at all is not named: it has not shown what it
    fits. One the clock cut down is named, because a residual it actually
    reached is a fact about the data whether or not the machine was fast
    enough to check it twice.
    """
    factor = float(settings["residual_factor"])
    spread_max = float(settings["spread_max"])
    beaten = [item for item in candidates
              if item.specs and item.spread > spread_max
              and item.rmse_rhoxx * factor < rmse_rhoxx]
    if not beaten or not np.isfinite(rmse_rhoxx):
        return "", float("nan")
    best = min(beaten, key=lambda item: item.rmse_rhoxx)
    return best.label, float(rmse_rhoxx / best.rmse_rhoxx)


def counts_to_try(kind: str, bounds) -> range:
    """How many carriers of one sign the search tries. FR-082, FR-013.

    The spectrum's count is the bound. Where it found no peak of a sign, zero
    belongs in the search: FR-013 permits a model of all one sign, and forcing
    one carrier of the other invents what the data did not ask for. Measured
    on a two-hole sweep with no electrons at all, where the spectrum proposed
    `hole 2, electron 0`: the search returned `1h+1e` with the electron pinned
    at its density bound, mobility 8.6, carrying 15 % of the conduction. Only
    the `free` gate caught it -- the share is far above what `earns` refuses --
    and `2h+0e` was never tried.

    One is still tried in that case, because a spectrum that found no peak of a
    sign may be wrong about it. Where the spectrum did find peaks the range is
    unchanged, so a sample with both signs costs exactly what it did before.
    """
    found = int(bounds["count"][kind])
    return range(0 if found == 0 else 1, max(1, found) + 1)


def residual_scale(candidates, settings) -> float:
    """The residual the `fits` gate is measured against. FR-085.

    Reproducible fits only. A degenerate fit reaches a lower residual by having
    more freedom than the data constrains, and letting it set the bar rejected
    2h+2e at 30 and 40 K on this project's twelve sweeps -- the answer research
    004 section 6 obtained fitting each sweep alone -- leaving no combination
    that passed.

    Its own function because the verdict is reached twice: once over the
    combinations the search tried, and again over the fit that is actually
    reported once the mobility window is released.
    """
    reproducible = [item for item in candidates
                    if item.spread <= float(settings["spread_max"])]
    return min(item.rmse_rhoxx for item in (reproducible or candidates))


def select(candidates, settings):
    """The smallest combination passing every gate, or the nearest miss. FR-086."""
    if not candidates:
        return None, [], {}
    best_rmse = residual_scale(candidates, settings)
    ordered = sorted(candidates, key=lambda c: (c.n_carriers, c.n_hole))
    scored = [(item, gates_of(item, best_rmse, settings)) for item in ordered]

    passing = [item for item, gates in scored if all(gates.values())]
    if passing:
        chosen = min(passing, key=lambda c: (c.n_carriers, c.rmse_rhoxx))
        return chosen, [], dict(gates_of(chosen, best_rmse, settings))

    fitting_ones = [(item, gates) for item, gates in scored if gates["fits"]]
    pool = fitting_ones or scored
    chosen, gates = min(
        pool,
        key=lambda pair: (sum(1 for name, ok in pair[1].items()
                              if not ok and name != "fits"),
                          pair[0].n_carriers, pair[0].rmse_rhoxx),
    )
    return chosen, [name for name, ok in gates.items() if not ok], dict(gates)


# ------------------------------------------------------------------ the modes

@dataclass(frozen=True)
class TemperatureOutcome:
    """What one count rule made of one sweep. `mode` holds the rule."""

    T_K: float
    mode: str
    n_hole: int
    n_electron: int
    grade: str
    r2_rhoxx: float
    r2_rhoxy: float
    rmse_rhoxx: float
    rmse_rhoxy: float
    condition_number: float
    spread: float
    seconds: float
    bounds: dict[str, Any]
    carriers: tuple[dict[str, Any], ...]
    candidates: tuple[Candidate, ...] = ()
    failed_gates: tuple[str, ...] = ()
    escaped_window: tuple[str, ...] = ()
    # FR-085. A combination that fits better than the chosen one by more than
    # the residual factor but does not reproduce, and how many times better.
    # Reported beside the verdict, never used to choose: it says the data asks
    # for more freedom than it can determine.
    undetermined_better: str = ""
    undetermined_ratio: float = float("nan")
    # FR-082. The data rule chose more carriers of some sign than the
    # spectrum's peaks proposed, because the larger combination fitted better
    # by more than the residual factor and reproduced.
    beyond_bound: bool = False
    # FR-087. How well the answer describes the sweep, on the scale of the
    # measurement: the noise of each channel, the RMSE over it, and the runs
    # test of the residual. The grade says whether the parameters are
    # determined; these say whether the curve is followed. Research 004
    # section 6.2 measured the two ranking the high-temperature sweeps in
    # opposite orders.
    noise_rhoxx: float = float("nan")
    noise_rhoxy: float = float("nan")
    residual_over_noise_xx: float = float("nan")
    residual_over_noise_xy: float = float("nan")
    runs_z_xx: float = float("nan")
    runs_z_xy: float = float("nan")
    # FR-090. Both neighbours agreed on a count and this sweep did not; the
    # label is theirs, and the price is how many times worse the residual gets
    # when this sweep is held to it. Reported, never acted on.
    island_label: str = ""
    island_price: float = float("nan")
    # FR-081. The spectrum that bounded this sweep's search, as a curve. Its
    # conclusions -- a count and a window -- are in `bounds`; this is the
    # picture they were read from.
    spectrum: dict[str, Any] = field(default_factory=dict)
    iterations: int = 1
    # The peaks rule only: why its loop stopped. "converged", "max_iterations",
    # "fit_out_of_budget" or "no_peaks". A bare iteration count hid, once, a
    # loop that never ran (research 004 section 4.1).
    stop_reason: str = ""

    @property
    def label(self) -> str:
        return f"{self.n_hole}h+{self.n_electron}e"

    @property
    def determined(self) -> bool:
        """FR-086. A grade is not a pass: the gates decide that."""
        return not self.failed_gates


def _carrier_document(carriers, window=None):
    """Carrier specifications for `config.resolve`, in boundary units."""
    out = []
    for index, item in enumerate(carriers, start=1):
        kind = item["kind"]
        low, high = window[kind] if window else (1.0, 1e6)
        mobility = float(np.clip(item["mobility_cm2Vs"], low, high))
        out.append({
            "name": f"{kind[0]}{index}",
            "kind": kind,
            "density": {"init": float(item["density_cm3"]), "min": 1e15, "max": 1e23},
            "mobility": {"init": mobility, "min": float(low), "max": float(high)},
        })
    return out


def _fit_one(path, base_document, carriers, window, starts, budget, hooks=_QUIET, *, T_K):
    """One combination at one temperature, inside a wall-clock budget. FR-088.

    `T_K` is required and names the sweep that is fitted. The table at `path`
    may hold every temperature, and fitting all of them to keep the first
    returned the lowest temperature's answer at every temperature -- the
    twelve-sweep run through the page reported 10 K with 5 K's condition
    number to eight digits -- while fitting twelve sweeps per combination.
    """
    hooks.check()
    document = json.loads(json.dumps(base_document))
    document["carriers"] = _carrier_document(carriers, window)
    document.setdefault("optimization", {})["multi_start"] = int(starts)
    document["optimization"]["fit_budget_s"] = float(budget)
    document.setdefault("spectrum", {})["enabled"] = False
    config = resolve(document)
    loaded = load_dataset(path, config)
    groups = tuple(g for g in loaded.groups if abs(g.T_K - float(T_K)) <= 1e-6)
    if len(groups) != 1:
        raise ValueError(f"expected one sweep at {T_K} K, found {len(groups)}")
    dataset = Dataset(groups=groups, n_records_dropped=loaded.n_records_dropped)

    started = time.monotonic()
    try:
        result = fit_dataset(dataset, config)
    except MbfitError as exc:
        # Every start ran out of budget before one finished. FR-084 still wants
        # the combination recorded, so the caller gets None and an expiry.
        if getattr(exc, "code", "") == "E_FIT_NO_START":
            return None, True, time.monotonic() - started
        raise
    seconds = time.monotonic() - started
    fit = result.fits[0]
    # FR-088. `fitting.fit_temperature` abandons a start that runs past the
    # budget, so a fit that lost starts to it is one the budget bit into.
    expired = len(fit.starts) < int(config.optimization["multi_start"])
    return fit, expired, seconds


def _candidate_from(fit, n_hole, n_electron, expired, seconds, equivalence):
    n, mu = split_parameters(fit.params)
    share = n * ELEMENTARY_CHARGE_C * mu
    return Candidate(
        n_hole=n_hole, n_electron=n_electron,
        rmse_rhoxx=float(fit.rmse_rhoxx), rmse_rhoxy=float(fit.rmse_rhoxy),
        r2_rhoxx=float(fit.r2_rhoxx), r2_rhoxy=float(fit.r2_rhoxy),
        condition_number=float(fit.condition_number),
        spread=spread_of(fit, equivalence),
        weakest_share=float(share.min() / share.sum()) if share.sum() > 0 else 0.0,
        at_bound=bool(np.any(fit.at_bound_low) or np.any(fit.at_bound_high)),
        expired=bool(expired), n_starts=len(fit.starts), seconds=float(seconds),
        params=fit.params, specs=fit.specs,
    )


def _expired_candidate(n_hole, n_electron, seconds) -> Candidate:
    """A combination whose every start ran out of budget. FR-084, FR-088.

    Recorded rather than dropped, so the list of candidates still covers the
    whole bound. It can never be selected: an infinite residual fails the
    first gate, and no start finished, so its spread was never measured and
    fails the second.
    """
    return Candidate(
        n_hole=n_hole, n_electron=n_electron,
        rmse_rhoxx=float("inf"), rmse_rhoxy=float("inf"),
        r2_rhoxx=float("nan"), r2_rhoxy=float("nan"),
        condition_number=float("inf"), spread=float("inf"),
        weakest_share=0.0, at_bound=False, expired=True, n_starts=0,
        seconds=float(seconds), params=np.array([]), specs=(),
    )


def data_rule(path, base_document, entry, settings, equivalence,
             hooks=_QUIET) -> TemperatureOutcome:
    """The spectrum bounds the search; the fit gives the answer. FR-080.

    Every combination up to the bound is fitted, because stopping at the first
    acceptable one hides how close the alternatives came (FR-084). The cost of
    that is the point of the budget: research 004 section 2 measures the fits
    that were actually selected totalling 67 seconds across twelve
    temperatures, against 4913 for the whole search.
    """
    started = time.monotonic()
    bounds = bounds_from(entry, float(settings["window_factor"]))
    total = float(sum(np.sum(branch.density) for branch in entry.branches))

    candidates = []
    for n_hole in counts_to_try("hole", bounds):
        for n_electron in counts_to_try("electron", bounds):
            if n_hole + n_electron == 0:
                continue                      # a model of nothing fits nothing
            seeds = []
            for kind, wanted in (("hole", n_hole), ("electron", n_electron)):
                branch = entry.branch(kind)
                got = segment_seeds(branch.mu_grid_m2Vs * 1e4, branch.density,
                                    entry.sigma_xx_zero, total, wanted)
                if len(got) < wanted:
                    low, high = bounds["window"][kind]
                    got = [{"mobility_cm2Vs": float(m), "density_cm3": 1e20}
                           for m in np.geomspace(high, low, wanted)]
                seeds.extend(dict(item, kind=kind) for item in got[:wanted])
            hooks.report(stage="search", T_K=float(entry.T_K),
                         holes=n_hole, electrons=n_electron,
                         max_holes=max(1, bounds["count"]["hole"]),
                         max_electrons=max(1, bounds["count"]["electron"]))
            fit, expired, seconds = _fit_one(
                path, base_document, seeds, bounds["window"],
                settings["search_multi_start"], float(settings["fit_budget_s"]),
                hooks, T_K=entry.T_K)
            if fit is None:
                candidates.append(_expired_candidate(n_hole, n_electron, seconds))
                continue
            candidates.append(_candidate_from(fit, n_hole, n_electron,
                                              expired, seconds, equivalence))

    fitted = [item for item in candidates if item.specs]
    chosen, failed, _ = select(fitted, settings)
    if chosen is None:
        raise ValueError("no combination could be fitted at this temperature")

    # FR-082. The peak count is a bound that held on most of this project's
    # sweeps and not on all of them: near the transition the spectrum merged
    # channels, proposed one carrier of each sign, and the search never tried
    # the 2h+2e that fits 2.5 to 5 times better. So the count grows past the
    # bound one step at a time for as long as FR-085 moves to the larger
    # combination, and stops the first time it does not.
    limit = int(settings["max_per_sign"])
    tried = {(item.n_hole, item.n_electron) for item in candidates}
    while True:
        steps = growth_of(chosen.n_hole, chosen.n_electron, tried, limit)
        if not steps:
            break
        for n_hole, n_electron in steps:
            tried.add((n_hole, n_electron))
            seeds = []
            for kind, wanted in (("hole", n_hole), ("electron", n_electron)):
                branch = entry.branch(kind)
                got = segment_seeds(branch.mu_grid_m2Vs * 1e4, branch.density,
                                    entry.sigma_xx_zero, total, wanted)
                if len(got) < wanted:
                    low, high = bounds["window"][kind]
                    got = [{"mobility_cm2Vs": float(m), "density_cm3": 1e20}
                           for m in np.geomspace(high, low, wanted)]
                seeds.extend(dict(item, kind=kind) for item in got[:wanted])
            hooks.report(stage="beyond", T_K=float(entry.T_K),
                         holes=n_hole, electrons=n_electron)
            # No window: the window was drawn around the peaks that proposed
            # too few carriers.
            fit, expired, seconds = _fit_one(
                path, base_document, seeds, None,
                settings["search_multi_start"], float(settings["fit_budget_s"]),
                hooks, T_K=entry.T_K)
            if fit is None:
                candidates.append(_expired_candidate(n_hole, n_electron, seconds))
            else:
                candidates.append(_candidate_from(fit, n_hole, n_electron,
                                                  expired, seconds, equivalence))
        fitted = [item for item in candidates if item.specs]
        moved, moved_failed, _ = select(fitted, settings)
        if moved is None or not grows_the_fit(chosen, moved, settings):
            break
        chosen, failed = moved, moved_failed

    beyond = (chosen.n_hole > max(1, bounds["count"]["hole"])
              or chosen.n_electron > max(1, bounds["count"]["electron"]))
    warning = undetermined_better_of(fitted, chosen.rmse_rhoxx, settings)

    # FR-082 is a bound on the search, not on the answer: release it and see
    # whether the answer stays inside. One that walks out was being held.
    n, mu = split_parameters(chosen.params)
    released = [{"kind": spec.kind, "density_cm3": float(a),
                 "mobility_cm2Vs": float(b)}
                for spec, a, b in zip(chosen.specs, n, mu)]
    hooks.report(stage="release", T_K=float(entry.T_K),
                 holes=chosen.n_hole, electrons=chosen.n_electron)
    fit, expired, seconds = _fit_one(
        path, base_document, released, None,
        settings["final_multi_start"], float(settings["fit_budget_s"]), hooks,
        T_K=entry.T_K)
    if fit is not None:
        chosen = _candidate_from(fit, chosen.n_hole, chosen.n_electron,
                                 expired, seconds, equivalence)
        # FR-085, FR-086. The answer reported is this fit, so the verdict
        # reported has to be this fit's. Releasing the window can cost a fit
        # its reproducibility or walk a carrier onto a declared bound, and it
        # can equally clear a failure the windowed fit had. Carrying the
        # search's verdict across described a fit that was not the answer.
        # The scale stays the search's: FR-085 measures against the best any
        # reproducible combination reached, and that is what the search found.
        gates = gates_of(chosen, residual_scale(fitted, settings), settings)
        failed = [name for name, ok in gates.items() if not ok]
        warning = undetermined_better_of(fitted, chosen.rmse_rhoxx, settings)
        n, mu = split_parameters(fit.params)
        specs = fit.specs
    else:
        specs = chosen.specs

    share = n * ELEMENTARY_CHARGE_C * mu
    carriers = []
    for spec, density, mobility, weight in zip(specs, n, mu, share):
        carriers.append({"name": spec.name, "kind": spec.kind,
                         "density_cm3": float(density),
                         "mobility_cm2Vs": float(mobility),
                         "conduction_share": float(weight / share.sum()),
                         "mu_B_at_9T": float(mobility * 1e-4 * 9.0)})
    carriers, escaped = _named_by_density(carriers, bounds)

    return TemperatureOutcome(
        T_K=float(entry.T_K), mode=DATA_RULE, spectrum=spectrum_curves(entry),
        n_hole=chosen.n_hole, n_electron=chosen.n_electron,
        grade=grade_of(chosen.condition_number),
        r2_rhoxx=chosen.r2_rhoxx, r2_rhoxy=chosen.r2_rhoxy,
        rmse_rhoxx=chosen.rmse_rhoxx, rmse_rhoxy=chosen.rmse_rhoxy,
        condition_number=chosen.condition_number, spread=chosen.spread,
        seconds=time.monotonic() - started, bounds=bounds,
        carriers=tuple(carriers), candidates=tuple(candidates),
        failed_gates=tuple(failed), escaped_window=tuple(escaped),
        undetermined_better=warning[0], undetermined_ratio=warning[1],
        beyond_bound=bool(beyond),
    )


def grows_the_fit(chosen: Candidate, moved: Candidate, settings) -> bool:
    """Whether the search past the bound may move from `chosen` to `moved`. FR-082.

    Only to a larger combination whose residual is smaller by more than the
    residual factor. Selection alone is not enough: at 100 K the search's best,
    `1h+1e`, failed the bound gate, a `1h+2e` with a larger residual passed
    every gate, and FR-085 -- which prefers any pass to any miss -- moved to it,
    taking the residual from `11.4` to `14.6` times the noise. Growing the count
    is for fitting better; a gate the smaller combination failed stays reported.
    """
    return (moved.label != chosen.label
            and moved.n_carriers > chosen.n_carriers
            and moved.rmse_rhoxx * float(settings["residual_factor"]) < chosen.rmse_rhoxx)


def growth_of(n_hole: int, n_electron: int, tried, limit: int):
    """The next combinations to try past the bound: one more of either sign, or both.

    Skips what was already fitted and anything over `limit` per sign. FR-082.
    """
    steps = []
    for extra_hole, extra_electron in ((1, 0), (0, 1), (1, 1)):
        step = (n_hole + extra_hole, n_electron + extra_electron)
        if step in tried or step[0] > limit or step[1] > limit:
            continue
        steps.append(step)
    return steps


def with_fit_quality(outcome: TemperatureOutcome, group, polarity: float) -> TemperatureOutcome:
    """FR-087. The answer's residual on the scale of the measurement."""
    import dataclasses

    noise_xx = noise_second_difference(group.rhoxx_uohmcm)
    noise_xy = noise_second_difference(group.rhoxy_uohmcm)
    if not outcome.carriers:
        return dataclasses.replace(outcome, noise_rhoxx=noise_xx, noise_rhoxy=noise_xy)
    model_xx, model_xy = _model_of(group, list(outcome.carriers), polarity)
    residual_xx = group.rhoxx_uohmcm - model_xx
    residual_xy = group.rhoxy_uohmcm - model_xy
    rms_xx = float(np.sqrt(np.mean(residual_xx ** 2)))
    rms_xy = float(np.sqrt(np.mean(residual_xy ** 2)))
    return dataclasses.replace(
        outcome, noise_rhoxx=noise_xx, noise_rhoxy=noise_xy,
        residual_over_noise_xx=rms_xx / noise_xx if noise_xx > 0 else float("nan"),
        residual_over_noise_xy=rms_xy / noise_xy if noise_xy > 0 else float("nan"),
        runs_z_xx=float(runs_test_z(residual_xx)), runs_z_xy=float(runs_test_z(residual_xy)),
    )


def peak_rule(path, base_document, entry, settings, equivalence,
              config, group, hooks=_QUIET) -> TemperatureOutcome:
    """The count the spectrum's peaks give, held, and the loop of Liu et al. FR-080.

    Supplemental Material section III, steps 2 to 4: read each peak as a
    carrier (step 3.3), start a multiband fit at that count from those values
    (step 4), feed the fitted carriers back as the starting point of the
    Lorentzian extension (step 2.1), recompute the spectrum, and repeat until
    the fitted densities and mobilities converge. The answer is the last fit.

    The count is whatever the current spectrum's peaks say, so it may change
    between passes; convergence is only declared between two fits of the same
    count. The gates of FR-085 are evaluated and reported but choose nothing,
    since there is nothing to choose between -- which is how a reader sees that
    a held count left the parameters undetermined.

    One carrier becomes one extension term: a hole seeds `(p, q) = (w, 0)` and
    an electron `(0, w)`, where `w` is its share of the zero-field
    conductivity, which the normalisation of FR-067 makes the weights mean.
    """
    started = time.monotonic()
    spectrum_settings = dict(config.spectrum)
    tolerance = float(settings["loop_tolerance"])
    max_iterations = int(settings["loop_max_iterations"])
    bounds = bounds_from(entry, float(settings["window_factor"]))

    current = entry
    fit = candidate = None
    previous = None
    passes = 0
    stop_reason = "max_iterations"

    for _ in range(max_iterations):
        seeds = []
        for kind in ("hole", "electron"):
            seeds.extend(
                dict(item, kind=kind)
                for item in spectrum_module.carriers_from(current.branch(kind),
                                                          current.sigma_xx_zero)
            )
        if not seeds:
            stop_reason = "no_peaks"
            break
        n_hole = sum(1 for item in seeds if item["kind"] == "hole")
        n_electron = len(seeds) - n_hole

        hooks.report(stage="peaks", T_K=float(entry.T_K), iteration=passes + 1,
                     holes=n_hole, electrons=n_electron)
        got, expired, seconds = _fit_one(path, base_document, seeds, None,
                                         settings["peaks_multi_start"],
                                         float(settings["peaks_fit_budget_s"]), hooks,
                                         T_K=entry.T_K)
        if got is None:
            stop_reason = "fit_out_of_budget"
            break
        fit = got
        candidate = _candidate_from(got, n_hole, n_electron, expired, seconds, equivalence)
        passes += 1

        density, mobility = split_parameters(got.params_canonical)
        vector = np.concatenate([density, mobility])
        if previous is not None and previous.size == vector.size:
            moved = float(np.max(np.abs(vector / previous - 1.0)))
            if moved < tolerance:
                stop_reason = "converged"
                break
        previous = vector

        seed = _extension_seed(got, current, spectrum_settings)
        current = spectrum_module.for_temperature(got, group, config, seed=seed)

    if fit is None:
        nan = float("nan")
        return TemperatureOutcome(
            T_K=float(entry.T_K), mode=PEAK_RULE, n_hole=0, n_electron=0, grade="-",
            r2_rhoxx=nan, r2_rhoxy=nan, rmse_rhoxx=nan, rmse_rhoxy=nan,
            condition_number=nan, spread=nan, seconds=time.monotonic() - started,
            bounds=bounds, spectrum=spectrum_curves(entry), carriers=(),
            iterations=passes, stop_reason=stop_reason,
            failed_gates=("fits",),
        )

    density, mobility = split_parameters(fit.params)
    share = density * ELEMENTARY_CHARGE_C * mobility
    carriers = [{"name": spec.name, "kind": spec.kind,
                 "density_cm3": float(value), "mobility_cm2Vs": float(speed),
                 "conduction_share": float(weight / share.sum()),
                 "mu_B_at_9T": float(speed * 1e-4 * 9.0)}
                for spec, value, speed, weight
                in zip(fit.specs, density, mobility, share)]
    carriers, escaped = _named_by_density(carriers, bounds)
    gates = gates_of(candidate, candidate.rmse_rhoxx, settings)
    return TemperatureOutcome(
        T_K=float(entry.T_K), mode=PEAK_RULE, spectrum=spectrum_curves(entry),
        n_hole=candidate.n_hole, n_electron=candidate.n_electron,
        grade=grade_of(candidate.condition_number),
        r2_rhoxx=candidate.r2_rhoxx, r2_rhoxy=candidate.r2_rhoxy,
        rmse_rhoxx=candidate.rmse_rhoxx, rmse_rhoxy=candidate.rmse_rhoxy,
        condition_number=candidate.condition_number, spread=candidate.spread,
        seconds=time.monotonic() - started, bounds=bounds,
        carriers=tuple(carriers), candidates=(candidate,),
        failed_gates=tuple(name for name, ok in gates.items() if not ok),
        escaped_window=tuple(escaped), iterations=passes, stop_reason=stop_reason,
    )


def _extension_seed(fit, entry, settings):
    """The fitted carriers as a starting point for the next extension.

    One carrier is one term: the hole weight `p` or the electron weight `q`
    takes that carrier's share of `sigma_xx(0)` and the other is zero. Spare
    terms, where the extension has more than the fit has carriers, start
    spread over the declared range carrying nothing.
    """
    n_terms = int(settings["lorentzian_terms"])
    density, mobility = split_parameters(fit.params)
    kinds = [spec.kind for spec in fit.specs]
    sigma0 = entry.sigma_xx_zero
    # sigma_xx(0) is SI; n q mu in boundary units becomes S/cm, hence the 1e-2
    share = density * ELEMENTARY_CHARGE_C * mobility / (sigma0 * 1e-2)
    mobilities = np.asarray(mobility, dtype=float) * 1e-4      # cm^2/Vs -> m^2/Vs

    p = np.array([w if k == "hole" else 0.0 for w, k in zip(share, kinds)])
    q = np.array([0.0 if k == "hole" else w for w, k in zip(share, kinds)])
    if mobilities.size < n_terms:
        spare = n_terms - mobilities.size
        low = float(settings["mu_min_cm2Vs"]) * 1e-4
        high = float(settings["mu_max_cm2Vs"]) * 1e-4
        pad = np.geomspace(high, low, spare + 2)[1:-1]
        mobilities = np.concatenate([mobilities, pad])
        p = np.concatenate([p, np.zeros(spare)])
        q = np.concatenate([q, np.zeros(spare)])
    else:
        order = np.argsort(-mobilities)[:n_terms]
        mobilities, p, q = mobilities[order], p[order], q[order]
    return p, q, mobilities


def _model_of(group, carriers, polarity):
    from .core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
    from .core.units import density_to_si, mobility_to_si, resistivity_from_si

    if not carriers:
        nan = np.full(group.B_T.size, np.nan)
        return nan, nan
    density = density_to_si(np.array([c["density_cm3"] for c in carriers]))
    mobility = mobility_to_si(np.array([c["mobility_cm2Vs"] for c in carriers]))
    sign = np.array([SIGN_HOLE if c["kind"] == "hole" else SIGN_ELECTRON
                     for c in carriers], dtype=float)
    xx, xy = resistivity(group.B_T, density, mobility, sign, polarity)
    return resistivity_from_si(xx), resistivity_from_si(xy)


def _r_squared(model, measured):
    measured = np.asarray(measured, dtype=float)
    model = np.asarray(model, dtype=float)
    if not np.all(np.isfinite(model)):
        return float("nan")
    total = float(np.sum((measured - measured.mean()) ** 2))
    if total <= 0.0:
        return float("nan")
    return 1.0 - float(np.sum((model - measured) ** 2)) / total


def _rmse(model, measured):
    model = np.asarray(model, dtype=float)
    if not np.all(np.isfinite(model)):
        return float("nan")
    return float(np.sqrt(np.mean((model - np.asarray(measured, dtype=float)) ** 2)))


# ------------------------------------------------------------ the entry point

@dataclass(frozen=True)
class WorkflowResult:
    """Every temperature, under one count rule."""

    mode: str
    outcomes: tuple[TemperatureOutcome, ...]
    seconds: float
    # Carried so the report can draw the measurement against the fit without
    # loading and resolving the data a second time.
    dataset: Any = None
    hall_polarity: float = 1.0

    @property
    def temperatures(self) -> tuple[float, ...]:
        return tuple(item.T_K for item in self.outcomes)

    def at(self, T_K: float) -> TemperatureOutcome:
        for item in self.outcomes:
            if item.T_K == T_K:
                return item
        raise KeyError(T_K)


def analyse(path, document, mode=None, hooks=None) -> WorkflowResult:
    """The whole procedure, one count rule, every temperature. FR-080.

    `document` is a configuration document, not a resolved one, because both
    rules fit at counts the document does not declare and each of those needs
    its own resolution. `mode` is the rule, `"data"` or `"peaks"`; without one
    the document's `workflow.count` decides, and its default is `"data"`.

    The spectrum is computed temperature by temperature inside the main loop
    rather than all at once beforehand -- the same computation as
    `spectrum.estimate`, in a different order -- so a run that is stopped
    keeps every temperature it finished (FR-098).
    """
    hooks = hooks or _QUIET
    started = time.monotonic()
    base = json.loads(json.dumps(document))
    base.setdefault("spectrum", {})["enabled"] = True
    config = resolve(base)
    settings = dict(config.workflow)
    chosen = str(mode or settings["count"])
    if chosen not in MODES:
        raise ValueError(f"count rule must be one of {MODES}, not {chosen!r}")
    polarity = float(config.model["hall_polarity"])

    dataset = load_dataset(path, config)
    total = len(dataset.groups)
    hooks.report(stage="prepare", index=0, total=total)
    hooks.check()
    # FR-098. The preparatory fit is one call over every temperature, and it is
    # the longest stretch of an analysis in which nothing else is asked. Until
    # the stop reached it, pressing stop during preparation was answered only
    # after all twelve sweeps had been fitted.
    # Only the stop. `fit_dataset` hands the same `progress` to the coupled
    # strategy, which calls it with keywords of its own, so a callback shaped
    # for the per-temperature strategies breaks that one.
    try:
        declared = fit_dataset(dataset, config, stop=hooks.stop)
    except FitStopped:
        raise Cancelled([], dataset, polarity) from None
    equivalence = float(config.acceptance["cost_equivalence"])
    fixed = pinned_counts(settings.get("fixed_counts"))

    outcomes = []
    # Kept for the second pass: whether a sweep is an island cannot be known
    # until the sweep after it has an answer, and pricing one needs its
    # spectrum back (FR-090).
    entries = []
    try:
        for index, (declared_fit, group) in enumerate(zip(declared.fits, dataset.groups)):
            hooks.report(stage="spectrum", T_K=float(group.T_K), index=index, total=total)
            hooks.check()
            entry = spectrum_module.for_temperature(declared_fit, group, config)
            entries.append(entry)
            hooks.report(stage="temperature", T_K=float(group.T_K), index=index, total=total)
            if chosen == PEAK_RULE:
                outcome = peak_rule(path, base, entry, settings, equivalence,
                                    config, group, hooks)
            else:
                outcome = data_rule(path, base, entry, settings, equivalence, hooks)
                held = count_for(entry.T_K, fixed)
                if held is not None and (outcome.n_hole, outcome.n_electron) != tuple(held):
                    pinned = _refit_at(path, base, entry, settings, equivalence,
                                       int(held[0]), int(held[1]), outcome, hooks)
                    # A pin that would not fit is said out loud. Keeping the
                    # count the reader overrode, and saying nothing, leaves the
                    # document and the answer disagreeing about what was run.
                    outcome = (pinned if pinned is not None
                               else replace(outcome, stop_reason="pin_not_fitted"))
            outcomes.append(with_fit_quality(outcome, group, polarity))

        outcomes = _price_the_islands(path, base, entries, outcomes, dataset.groups,
                                      settings, equivalence, polarity, hooks)
        # FR-112. Last, because a coupling acts on a band already held to one
        # count: the pinning above is what makes the sweeps one series.
        outcomes = _apply_smooth_bands(base, outcomes, dataset.groups, settings,
                                       equivalence, polarity, hooks)
    except Cancelled as stopped:
        raise Cancelled(outcomes, dataset, polarity) from stopped

    hooks.report(stage="done", index=total, total=total)
    return WorkflowResult(mode=chosen, outcomes=tuple(outcomes),
                          seconds=time.monotonic() - started, dataset=dataset,
                          hall_polarity=polarity)


def _apply_smooth_bands(base_document, outcomes, groups, settings, equivalence,
                        polarity, hooks=_QUIET):
    """FR-112. The bands a document asked to be coupled across temperature.

    This exists so that a coupled answer has a form a configuration document
    can carry. The coupling runs under a strategy the procedure never selects
    for itself, so without this the page could produce an answer the command
    line could not, and FR-107 forbids that.
    """
    declared = settings.get("smooth_band") or ()
    if not declared:
        return outcomes
    rows = list(outcomes)
    for band in declared:
        low, high = float(band["low"]), float(band["high"])
        chosen = [item for item in rows if item.carriers and low <= item.T_K <= high]
        if len(chosen) < 3:
            # A curvature needs three points. Refusing is the honest answer;
            # coupling two sweeps would report a constraint that did nothing.
            raise MbfitError("E_CONFIG_BAD_VALUE", path="workflow.smooth_band",
                             value=band["range"],
                             expected="a band of at least three sweeps that answered")
        counts = {(item.n_hole, item.n_electron) for item in chosen}
        if len(counts) != 1:
            raise MbfitError(
                "E_CONFIG_BAD_VALUE", path="workflow.smooth_band",
                value=band["range"],
                expected="one carrier count across the band; pin it with fixed_counts")
        wanted = [item.T_K for item in chosen]
        band_groups = [group for group in groups
                       if any(abs(group.T_K - T) <= 1e-6 for T in wanted)]
        coupled, _lam = smooth_band(base_document, chosen, band_groups, settings,
                                    equivalence, band["strength"], hooks)
        replaced = {item.T_K: with_fit_quality(item, group, polarity)
                    for item, group in zip(coupled, band_groups)}
        rows = [replaced.get(item.T_K, item) for item in rows]
    return rows


def islands_of(outcomes) -> dict[int, tuple[int, int]]:
    """Sweeps carrying more carriers than a count both neighbours share. FR-090.

    Two conditions, and both were learned by getting them wrong.

    The neighbours must agree with each other. Where they do not, the sweep
    sits inside a transition, and following a transition is exactly what the
    count must stay free to do; without this the step at the
    charge-density-wave transition would be marked as an anomaly.

    And the sweep must carry *more* carriers than they do. "Differs from both"
    is symmetric, and on this project's twelve sweeps it marked 60 K as well:
    its neighbours at 50 and 70 K both chose `2h+3e` and it chose `2h+2e`. That
    is not the failure being looked for. Freedom that appears at one
    temperature and is gone on either side claims a carrier that exists only
    there; carrying fewer carriers than the neighbours claims nothing. With
    both conditions the twelve sweeps mark 50 K and 70 K and nothing else.

    A sweep with no answer is not a count, so it neither is an island nor makes
    one of its neighbour.
    """
    found: dict[int, tuple[int, int]] = {}
    for index in range(1, len(outcomes) - 1):
        here, before, after = outcomes[index], outcomes[index - 1], outcomes[index + 1]
        if not (here.carriers and before.carriers and after.carriers):
            continue
        theirs = (before.n_hole, before.n_electron)
        if theirs != (after.n_hole, after.n_electron):
            continue
        if here.n_hole + here.n_electron > sum(theirs):
            found[index] = theirs
    return found


def _price_the_islands(path, base, entries, outcomes, groups, settings,
                       equivalence, polarity, hooks):
    """Mark every island and measure what its neighbours' count costs. FR-090.

    A count that appears at one temperature and at neither side of it claims a
    carrier that exists only there. The procedure judges each sweep alone and
    cannot see that; until now the reader had to notice it unaided, and then
    had no number for the alternative.

    Marking is not deciding. The verdict stays where the gates put it and the
    price is reported beside it, so that overriding the count is a choice made
    against a number rather than an impression.
    """
    islands = islands_of(outcomes)
    if not islands:
        return outcomes
    priced = list(outcomes)
    for index, (n_hole, n_electron) in islands.items():
        hooks.check()
        hooks.report(stage="island", T_K=float(outcomes[index].T_K),
                     holes=n_hole, electrons=n_electron)
        # The search's budget, not the pinned one: nobody asked for this fit.
        # It prices an island the procedure noticed on its own, and an analysis
        # must not grow by half an hour a sweep because of a note in the margin.
        held = _refit_at(path, base, entries[index], settings, equivalence,
                         n_hole, n_electron, outcomes[index], hooks,
                         starts=settings["final_multi_start"],
                         budget=float(settings["fit_budget_s"]))
        if held is None:
            continue                       # no start finished; nothing to price
        held = with_fit_quality(held, groups[index], polarity)
        mine = outcomes[index].rmse_rhoxx
        price = held.rmse_rhoxx / mine if mine > 0 else float("nan")
        priced[index] = replace(outcomes[index], island_label=held.label,
                                island_price=float(price))
    return priced


def pinned_counts(declared) -> tuple[tuple[tuple[float, float], tuple[int, int]], ...]:
    """FR-090's setting, as temperature ranges paired with the count to hold."""
    from .config import temperature_range
    return tuple(
        (temperature_range(str(key), "workflow.fixed_counts"),
         (int(value[0]), int(value[1])))
        for key, value in (declared or {}).items()
    )


def count_for(T_K: float, pinned) -> tuple[int, int] | None:
    """The count pinned for this temperature, or nothing. FR-090.

    The narrowest range wins, so one temperature inside a band can be given its
    own count without rewriting the band around it.
    """
    covering = [(high - low, counts) for (low, high), counts in pinned
                if low - 1e-6 <= float(T_K) <= high + 1e-6]
    if not covering:
        return None
    return min(covering, key=lambda item: item[0])[1]


def _refit_at(path, base, entry, settings, equivalence, n_hole, n_electron,
              searched, hooks=_QUIET, *, starts=None,
              budget=None) -> TemperatureOutcome | None:
    """FR-090. The reader holds the count fixed; the cost of that is reported.

    A series whose model changes underneath it is not a series -- `n(T)` cannot
    be plotted from fits that do not share a carrier set. So the count can be
    pinned, and what pinning it cost in residual is carried on the outcome
    rather than left for the reader to notice.

    Returns `None` when no starting point finished inside the budget. It used
    to return the outcome it was given, which reads as success: a reader who
    pinned `3h+3e` was handed back the very count they were overriding, with
    nothing to say the pin had not been applied. What that silence means
    differs by caller, so the decision belongs to them and not here.
    """
    bounds = bounds_from(entry, float(settings["window_factor"]))
    total = float(sum(np.sum(branch.density) for branch in entry.branches))
    seeds = []
    for kind, wanted in (("hole", n_hole), ("electron", n_electron)):
        branch = entry.branch(kind)
        got = segment_seeds(branch.mu_grid_m2Vs * 1e4, branch.density,
                            entry.sigma_xx_zero, total, wanted)
        if len(got) < wanted:
            low, high = bounds["window"][kind]
            got = [{"mobility_cm2Vs": float(m), "density_cm3": 1e20}
                   for m in np.geomspace(high, low, wanted)]
        seeds.extend(dict(item, kind=kind) for item in got[:wanted])

    hooks.report(stage="fixed", T_K=float(entry.T_K), holes=n_hole, electrons=n_electron)
    # A pinned count gets the pinned budget unless the caller says otherwise.
    # The search's budget prunes combinations nobody asked for; this one is
    # asked for, and cutting it short answers the reader with silence.
    fit, expired, seconds = _fit_one(
        path, base, seeds, None,
        int(settings["pinned_multi_start"] if starts is None else starts),
        float(settings["pinned_fit_budget_s"] if budget is None else budget),
        hooks, T_K=entry.T_K)
    if fit is None:
        return None
    return _outcome_from(fit, n_hole, n_electron, expired, seconds, searched,
                         settings, equivalence, bounds)


def _outcome_from(fit, n_hole, n_electron, expired, seconds, previous,
                  settings, equivalence, bounds) -> TemperatureOutcome:
    """One fit, as an outcome. Shared by every route that refits a sweep.

    `previous` supplies what the fit itself cannot know -- the candidates the
    search tried, the gates it failed, and the time already spent -- so that a
    refit is reported in the same terms as the answer it replaces. Kept in one
    place because two routes assembling this differently would drift.
    """
    candidate = _candidate_from(fit, n_hole, n_electron, expired, seconds, equivalence)
    warning = undetermined_better_of(previous.candidates, candidate.rmse_rhoxx, settings)
    density, mobility = split_parameters(fit.params)
    share = density * ELEMENTARY_CHARGE_C * mobility
    carriers = [{"name": spec.name, "kind": spec.kind,
                 "density_cm3": float(value),
                 "mobility_cm2Vs": float(speed),
                 "conduction_share": float(weight / share.sum()),
                 "mu_B_at_9T": float(speed * 1e-4 * 9.0)}
                for spec, value, speed, weight
                in zip(fit.specs, density, mobility, share)]
    carriers, escaped = _named_by_density(carriers, bounds)
    return TemperatureOutcome(
        T_K=previous.T_K, mode=DATA_RULE, spectrum=previous.spectrum,
        n_hole=n_hole, n_electron=n_electron,
        grade=grade_of(candidate.condition_number),
        r2_rhoxx=candidate.r2_rhoxx, r2_rhoxy=candidate.r2_rhoxy,
        rmse_rhoxx=candidate.rmse_rhoxx, rmse_rhoxy=candidate.rmse_rhoxy,
        condition_number=candidate.condition_number, spread=candidate.spread,
        seconds=previous.seconds + seconds, bounds=bounds,
        carriers=tuple(carriers), candidates=previous.candidates,
        failed_gates=previous.failed_gates, escaped_window=tuple(escaped),
        undetermined_better=warning[0], undetermined_ratio=warning[1],
    )


def _named_by_density(carriers, bounds):
    """Name carriers so the denser band of a sign carries the lower number.

    The name used to be the seed slot the fit started from, which says nothing
    about the band. The optimiser may land the dense carrier in either slot, so
    neighbouring sweeps swapped labels and a series smooth in its values read
    as one that jumped. Ordering by density within each sign makes the label
    follow the band. Holes keep the numbers before the electrons, as the seeds
    did, so `2h+3e` is still `h1 h2 e3 e4 e5`.

    This is the reported name only. The canonical order the fit is judged in --
    decreasing mobility, `core/canonical.py` -- is what `spread`, the
    resampling intervals and the diagnostics of FR-047 are built on, and it is
    unchanged.

    The window check rides along because it reports names, and reporting a
    name that no longer exists is worse than not reporting it.
    """
    def densest_first(kind):
        return sorted((c for c in carriers if c["kind"] == kind),
                      key=lambda c: -float(c["density_cm3"]))

    named, escaped = [], []
    for index, item in enumerate([*densest_first("hole"), *densest_first("electron")],
                                 start=1):
        low, high = bounds["window"][item["kind"]]
        renamed = {**item, "name": f"{item['kind'][0]}{index}"}
        speed = float(renamed["mobility_cm2Vs"])
        if speed < low * 0.999 or speed > high * 1.001:
            escaped.append(renamed["name"])
        named.append(renamed)
    return named, escaped


def _canonical_carriers(outcome) -> list[dict]:
    """Holes then electrons, each densest first, so rows line up across sweeps.

    The order the names already carry (`_named_by_density`). Sorting these by
    mobility while the names followed density would print `e2` above `e1`.
    """
    def densest_first(kind):
        return sorted((c for c in outcome.carriers if c["kind"] == kind),
                      key=lambda c: -float(c["density_cm3"]))
    return [*densest_first("hole"), *densest_first("electron")]


def roughness_of(outcomes, breaks=()) -> float:
    """How far a band is from a smooth series, in the coupling penalty's measure.

    The same quantity FR-027's penalty minimises, so the number on screen and
    the number the optimiser sees are one number. Spacing-aware (FR-031), so a
    5 K step and a 20 K step are not judged differently on that account.

    Returns `nan` where the question does not apply: under three temperatures
    there is no curvature to measure, and a band whose carrier count changes is
    not one series to begin with.
    """
    from .core.penalties import coupling_residual

    usable = sorted((item for item in outcomes if item.carriers), key=lambda i: i.T_K)
    if len(usable) < 3 or len({(i.n_hole, i.n_electron) for i in usable}) != 1:
        return float("nan")
    rows = [[value for carrier in _canonical_carriers(item)
             for value in (carrier["density_cm3"], carrier["mobility_cm2Vs"])]
            for item in usable]
    sign = np.array([1.0 if c["kind"] == "hole" else -1.0
                     for c in _canonical_carriers(usable[0])])
    residual = coupling_residual(
        np.log(np.asarray(rows, dtype=float)),
        np.asarray([item.T_K for item in usable], dtype=float), sign,
        order=2, lambda_density=1.0, lambda_mobility=1.0, breaks=tuple(breaks))
    if residual.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(residual ** 2)))


#: FR-025. The coupling strengths offered for a band, by name.
SMOOTHING_STRENGTHS = ("weak", "normal", "strong")


def smooth_band(base_document, outcomes, groups, settings, equivalence,
                strength: str, hooks=_QUIET):
    """A pinned band refitted as one problem, with the temperature coupling on.

    FR-025 makes the sweeps one problem and FR-027 to FR-031 supply the
    penalty. What is decided here is only where it acts: over a band already
    held to one carrier count, because a coupling across sweeps that do not
    share a carrier set has nothing to couple.

    No strength is free. Measured over 5 to 90 K on this project's sweeps, the
    weakest offered costs `5 %` of the residual at the worst sweep and removes
    `6 %` of the curvature; the strongest costs `131 %` and removes `65 %`.
    Below 60 K the series is already smooth and there is little to remove; from
    60 to 90 K it is rough for a reason, and that is where forcing it is a way
    of erasing the reason. So the price is returned beside the answer.
    """
    if strength not in SMOOTHING_STRENGTHS:
        raise ValueError(f"smoothing strength must be one of {SMOOTHING_STRENGTHS}")
    usable = sorted((item for item in outcomes if item.carriers), key=lambda i: i.T_K)
    if len(usable) < 3:
        raise ValueError("a smooth series needs at least three temperatures")
    if len({(i.n_hole, i.n_electron) for i in usable}) != 1:
        raise ValueError("every sweep in the band must hold the same carrier count")

    strengths = {"weak": float(settings["smoothing_weak"]),
                 "normal": float(settings["smoothing_normal"]),
                 "strong": float(settings["smoothing_strong"])}
    lam = strengths[strength]

    template = _canonical_carriers(usable[0])
    base = json.loads(json.dumps(base_document))
    base["carriers"] = _carrier_document(template, None)
    base.setdefault("spectrum", {})["enabled"] = False
    names = [carrier["name"] for carrier in base["carriers"]]
    base["initial_by_temperature"] = {
        f"{item.T_K:g}": {
            name: {"density": float(carrier["density_cm3"]),
                   "mobility": float(carrier["mobility_cm2Vs"])}
            for name, carrier in zip(names, _canonical_carriers(item))
        }
        for item in usable
    }
    # AC-040. Every temperature is seeded at the answer the pinned refit
    # already found, just above: this is a refinement of an answer in hand, not
    # a search. Randomised starts around it re-solve a solved problem, and
    # eight of them were the whole difference between three hours and
    # twenty-five minutes on a band of thirteen (research 005 section 6).
    base["optimization"] = dict(base.get("optimization", {}),
                                temperature_strategy="global_smooth",
                                multi_start=int(settings["smooth_multi_start"]))
    base["smoothing"] = {"enabled": True, "order": 2,
                         "lambda_density": lam, "lambda_mobility": lam,
                         "breaks_K": []}

    wanted = [item.T_K for item in usable]
    chosen = tuple(group for group in groups
                   if any(abs(group.T_K - T) <= 1e-6 for T in wanted))
    hooks.check()
    hooks.report(stage="smooth", index=0, total=len(chosen))
    started = time.monotonic()
    try:
        # The whole band is one call, so the watching has to happen inside it.
        # Reporting once here and going quiet is what made a coupled fit look
        # like a hung program for two hours.
        run = fit_dataset(
            Dataset(groups=chosen, n_records_dropped=0), resolve(base),
            progress=lambda **event: hooks.report(
                stage="smooth", index=0, total=len(chosen), **event),
            stop=hooks.stop)
    except FitStopped:
        raise Cancelled() from None
    seconds = time.monotonic() - started

    n_hole, n_electron = usable[0].n_hole, usable[0].n_electron
    coupled = []
    for fit, previous in zip(run.fits, usable):
        coupled.append(_outcome_from(
            fit, n_hole, n_electron, False, seconds / len(run.fits), previous,
            settings, equivalence, previous.bounds))
    return coupled, lam
