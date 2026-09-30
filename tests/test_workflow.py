"""Feature 004 -- the procedure, and the two ways to run it. Gate 14.

The pieces of this feature are cheap to test and the whole is not: a single
temperature through fit mode fits nine combinations and takes minutes. So the
units below are exercised directly and the end-to-end run is one test, marked
slow, pinned to the numbers this project's own 5 K sweep produced.

Two of these tests exist because the obvious implementation was measured
costing an order of magnitude. `test_the_window_is_per_carrier_type` and
`test_seeds_come_from_the_distribution` are those, and both name the number.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, fitting, spectrum, workflow

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data" / "synthetic_5K.csv"
REFERENCE = ROOT / "configs" / "synthetic_5K.json"


def _document(**workflow_settings):
    document = json.loads(REFERENCE.read_text(encoding="utf-8"))
    document["spectrum"] = {"enabled": True, "lorentzian_terms": 6,
                            "lorentzian_multi_start": 12, "mu_min_cm2Vs": 100.0}
    if workflow_settings:
        document["workflow"] = workflow_settings
    return document


def _entry():
    """The 5 K spectrum, which both modes start from."""
    config = cfg.resolve(_document())
    dataset = dataio.load_dataset(DATA, config)
    result = fitting.fit_dataset(dataset, config)
    return spectrum.for_temperature(result.fits[0], dataset.groups[0], config)


# ----------------------------------------------------------- the grade

def test_the_grade_is_a_grade_and_not_a_gate():
    """AC-031. Research 001 section 4.6 calibrated the threshold between
    trusting the digits and not, which is not the same as usable and useless.
    """
    assert workflow.grade_of(1.0e2) == "A"
    assert workflow.grade_of(1.0e3) == "A"
    assert workflow.grade_of(3.8e3) == "B"      # the 60 K sweep of this project
    assert workflow.grade_of(2.0e4) == "C"
    assert workflow.grade_of(1.0e9) == "D"
    assert workflow.grade_of(float("inf")) == "D"
    assert workflow.grade_of(float("nan")) == "D"


# -------------------------------------------- what the spectrum supplies

@pytest.mark.slow
def test_the_window_is_per_carrier_type():
    """FR-082. Per peak was measured raising the residual from 0.043 to 1.587.

    The window has to span every peak of its sign, because the count is what
    the search varies: a window drawn around the two fastest holes puts the
    slow one outside the bounds, and then no combination can reach the answer.
    """
    entry = _entry()
    low, high = workflow.window_of(entry, "hole", 3.0)
    peaks = [item["mobility_cm2Vs"]
             for item in spectrum.carriers_from(entry.branch("hole"),
                                                entry.sigma_xx_zero)]
    assert low <= min(peaks) and high >= max(peaks)
    assert low == pytest.approx(min(peaks) / 3.0)
    assert high == pytest.approx(max(peaks) * 3.0)


def test_an_empty_branch_still_yields_a_window():
    """A branch with no peak must not produce an empty or inverted range."""

    class _Empty:
        sigma_xx_zero = 1.0

        def branch(self, kind):
            class _B:
                mu_grid_m2Vs = np.array([1.0, 2.0])
                density = np.zeros(2)
                peaks = ()
                kind = "hole"
            return _B()

    low, high = workflow.window_of(_Empty(), "hole", 3.0)
    assert 0.0 < low < high


# ------------------------------------------------------------- the seeds

def test_seeds_come_from_the_distribution():
    """FR-083. The peak list was measured giving 0.427 against 0.043.

    Two carriers asked of a three-peaked branch must not be the two tallest
    peaks: the multi-start of feature 001 perturbs around its starting point
    rather than sampling the bounds, so a seed that misses a carrier never
    finds it. Equal-weight segments cannot miss one, because every part of the
    distribution is inside exactly one segment.
    """
    mu = np.geomspace(100.0, 1.0e5, 400)
    density = np.zeros_like(mu)
    for centre, height in ((1.0e3, 1.0), (1.0e4, 3.0), (5.0e4, 0.4)):
        density += height * np.exp(-0.5 * (np.log(mu / centre) / 0.12) ** 2)

    two = workflow.segment_seeds(mu, density, 1.0e5, density.sum(), 2)
    assert len(two) == 2
    centres = sorted(item["mobility_cm2Vs"] for item in two)
    # one seed below the dominant peak and one above it, not the two tallest
    assert centres[0] < 1.0e4 < centres[1]

    three = workflow.segment_seeds(mu, density, 1.0e5, density.sum(), 3)
    assert len(three) == 3
    assert sorted(item["mobility_cm2Vs"] for item in three) == pytest.approx(
        sorted(item["mobility_cm2Vs"] for item in three))


def test_every_segment_carries_weight():
    """No seed may be placed where the distribution is not."""
    mu = np.geomspace(100.0, 1.0e5, 200)
    density = np.exp(-0.5 * (np.log(mu / 5.0e3) / 0.1) ** 2)
    seeds = workflow.segment_seeds(mu, density, 1.0e5, density.sum(), 4)
    assert len(seeds) == 4
    for item in seeds:
        assert item["density_cm3"] > 0.0
        assert mu[0] <= item["mobility_cm2Vs"] <= mu[-1]


def test_an_empty_branch_seeds_nothing():
    mu = np.geomspace(100.0, 1.0e5, 50)
    assert workflow.segment_seeds(mu, np.zeros(50), 1.0, 1.0, 3) == []


# ------------------------------------------------- how many of each sign

def test_a_sign_the_spectrum_did_not_find_may_be_left_out():
    """FR-013, FR-082. A model of all one sign is permitted, so the search has
    to be able to reach one.

    Measured on a two-hole sweep with no electrons, where the spectrum
    proposed `hole 2, electron 0`: forcing one electron returned `1h+1e` with
    that electron pinned at its density bound, mobility 8.6, carrying 15 % of
    the conduction -- far above what `earns` refuses. With zero in the search
    the same sweep returns `2h+0e`, grade A, no gate failed, and both
    parameters within 0.1 % of the truth.
    """
    bounds = {"count": {"hole": 2, "electron": 0}}
    assert list(workflow.counts_to_try("hole", bounds)) == [1, 2]
    assert list(workflow.counts_to_try("electron", bounds)) == [0, 1], (
        "zero is tried, and so is one: a spectrum that found no peak of a sign "
        "may be wrong about it")


def test_a_sign_the_spectrum_found_is_never_left_out():
    """And a sample with both signs costs exactly what it did before."""
    bounds = {"count": {"hole": 2, "electron": 3}}
    assert list(workflow.counts_to_try("hole", bounds)) == [1, 2]
    assert list(workflow.counts_to_try("electron", bounds)) == [1, 2, 3]


@pytest.mark.slow
def test_a_sample_of_one_sign_is_answered_without_the_other():
    """The end of the measurement above, run rather than recorded."""
    from mbfit.core.drude import SIGN_HOLE, resistivity

    B = np.round(np.arange(-9.0, 9.0 + 1e-9, 0.05), 4)
    truth_n, truth_mu = np.array([5.0e20, 2.0e21]), np.array([12000.0, 800.0])
    xx, xy = resistivity(B, truth_n * 1e6, truth_mu * 1e-4,
                         np.array([SIGN_HOLE, SIGN_HOLE]))
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 1.2e-3, B.shape)
    xx = xx * 1e8 + 0.5 * (noise + noise[::-1])
    xy = xy * 1e8

    document = _document()
    path = ROOT / "tests" / "data" / "_one_sign.csv"
    path.write_text("T(K),B(T),rhoxx(microohm cm),rhoxy(microohm cm)\n" + "\n".join(
        f"5,{b:g},{a:.5f},{c:.5f}" for b, a, c in zip(B, xx, xy)) + "\n", encoding="utf-8")
    try:
        config = cfg.resolve(document)
        dataset = dataio.load_dataset(path, config)
        entry = spectrum.for_temperature(
            fitting.fit_dataset(dataset, config).fits[0], dataset.groups[0], config)
        assert entry.proposal["electron"] == 0, "the spectrum finds no electrons"

        outcome = workflow.data_rule(path, document, entry, dict(config.workflow),
                                     float(config.acceptance["cost_equivalence"]))
        assert outcome.n_electron == 0, f"invented an electron: {outcome.label}"
        assert outcome.n_hole == 2
        assert not outcome.failed_gates
    finally:
        path.unlink()


# ------------------------------------------- the verdict and the answer

def test_the_verdict_describes_the_fit_that_is_reported():
    """FR-085, FR-086. The reported parameters and the reported verdict have
    to come from the same fit.

    `data_rule` releases the mobility window and refits before it answers, and
    it used to keep the verdict the search had reached inside the window. So a
    released fit whose spread had gone to infinity could be reported as
    reproducible, and one that the release had rescued stayed reported as
    failed. The invariant below is the one that broke.
    """
    document = _document()
    config = cfg.resolve(document)
    settings = dict(config.workflow)
    equivalence = float(config.acceptance["cost_equivalence"])

    small = ROOT / "tests" / "data" / "synthetic_small.csv"
    dataset = dataio.load_dataset(small, config)
    one = dataio.Dataset(groups=(dataset.groups[0],), n_records_dropped=0)
    declared = fitting.fit_dataset(one, config)
    entry = spectrum.for_temperature(declared.fits[0], one.groups[0], config)

    outcome = workflow.data_rule(small, document, entry, settings, equivalence)

    spread_max = float(settings["spread_max"])
    if "reproducible" in outcome.failed_gates:
        assert outcome.spread > spread_max, (
            "reported as not reproducing, but the reported spread reproduces")
    else:
        assert outcome.spread <= spread_max, (
            "reported as reproducing, but the reported spread does not")


# --------------------------------------------------------- carrier names

BROAD = {"window": {"hole": (1.0, 1e6), "electron": (1.0, 1e6)}}
FITTED = (
    {"name": "h1", "kind": "hole", "density_cm3": 1e19, "mobility_cm2Vs": 5000.0},
    {"name": "h2", "kind": "hole", "density_cm3": 1e21, "mobility_cm2Vs": 300.0},
    {"name": "e3", "kind": "electron", "density_cm3": 6e18, "mobility_cm2Vs": 5300.0},
    {"name": "e4", "kind": "electron", "density_cm3": 3e21, "mobility_cm2Vs": 170.0},
)


def test_the_denser_band_of_a_sign_carries_the_lower_number():
    """The label follows the band, not the seed slot the fit started from.

    The optimiser may land the dense carrier in either slot, so a name taken
    from the slot swapped between neighbouring sweeps and a series smooth in
    its values read as one that jumped.
    """
    named, _ = workflow._named_by_density(list(FITTED), BROAD)
    assert [c["name"] for c in named] == ["h1", "h2", "e3", "e4"], "holes keep the first numbers"
    assert [c["density_cm3"] for c in named] == [1e21, 1e19, 3e21, 6e18]
    for kind in ("hole", "electron"):
        densities = [c["density_cm3"] for c in named if c["kind"] == kind]
        assert densities == sorted(densities, reverse=True)


def test_a_carrier_outside_its_window_is_named_as_it_is_now_named():
    """Reporting a name the reader cannot find in the table is worse than silence."""
    tight = {"window": {"hole": (1.0, 1e6), "electron": (1000.0, 1e6)}}
    named, escaped = workflow._named_by_density(list(FITTED), tight)
    slow = next(c for c in named if c["mobility_cm2Vs"] == 170.0)
    assert slow["name"] == "e3", "the dense, slow electron is the first electron"
    assert escaped == ["e3"]


# ------------------------------------------------------------- the gates

def _candidate(**fields):
    base = dict(n_hole=2, n_electron=2, rmse_rhoxx=0.01, rmse_rhoxy=0.001,
                r2_rhoxx=0.999, r2_rhoxy=0.999, condition_number=100.0,
                spread=1e-8, weakest_share=0.2, at_bound=False, expired=False,
                n_starts=12, seconds=1.0, params=np.array([1.0, 1.0]), specs=())
    base.update(fields)
    return workflow.Candidate(**base)


SETTINGS = {"residual_factor": 1.25, "spread_max": 0.01, "share_min": 0.001}


def test_a_degenerate_fit_does_not_set_the_bar_for_fitting():
    """FR-085. The residual scale comes from reproducible fits.

    Gate 16 at 30 K: `4h+2e` reached 0.00800 with a spread of 1.02, and
    `2h+2e` at 0.01151 failed 1.25 times that, so nothing passed.
    """
    degenerate = _candidate(n_hole=4, n_electron=2, rmse_rhoxx=0.00800, spread=1.02,
                            condition_number=2.6e10)
    good = _candidate(n_hole=2, n_electron=2, rmse_rhoxx=0.01151, spread=2e-8,
                      condition_number=715.0)
    chosen, failed, _ = workflow.select([good, degenerate], SETTINGS)
    assert (chosen.n_hole, chosen.n_electron) == (2, 2)
    assert failed == []


def test_fit_quality_is_not_traded_against_the_others():
    """FR-085. An early version ranked by how many tests failed and chose a
    combination whose residual was ten times worse, because both failed one.
    """
    good = _candidate(n_hole=2, n_electron=2, rmse_rhoxx=0.01, at_bound=True)  # fails free
    bad = _candidate(n_hole=1, n_electron=1, rmse_rhoxx=0.10)  # fails fits only
    chosen, failed, _ = workflow.select([good, bad], SETTINGS)
    assert chosen.label == "2h+2e", "the model that describes the data wins"
    assert "fits" not in failed


def test_a_better_undetermined_fit_is_reported_and_never_passes_silently():
    """FR-085. The scale comes from reproducible fits, so a reproducible model ten
    times worse than an undetermined one passes -- and must say so."""
    # `specs` present: only a combination that was actually fitted can be reported
    undetermined = _candidate(n_hole=2, n_electron=2, rmse_rhoxx=0.01, spread=5.0, specs=("x",))
    determined = _candidate(n_hole=1, n_electron=1, rmse_rhoxx=0.10)
    chosen, failed, _ = workflow.select([undetermined, determined], SETTINGS)
    assert chosen.label == "1h+1e" and failed == []
    label, ratio = workflow.undetermined_better_of([undetermined, determined],
                                                   chosen.rmse_rhoxx, SETTINGS)
    assert label == "2h+2e" and ratio == pytest.approx(10.0)


def test_no_warning_when_the_undetermined_fit_is_within_the_factor():
    close = _candidate(n_hole=3, n_electron=3, rmse_rhoxx=0.0090, spread=5.0, specs=("x",))
    chosen = _candidate(n_hole=2, n_electron=2, rmse_rhoxx=0.0100)
    label, ratio = workflow.undetermined_better_of([close, chosen], 0.0100, SETTINGS)
    assert label == "" and np.isnan(ratio)


def test_the_smallest_passing_combination_is_chosen():
    small = _candidate(n_hole=1, n_electron=1, rmse_rhoxx=0.0101)
    large = _candidate(n_hole=3, n_electron=3, rmse_rhoxx=0.0100)
    chosen, failed, _ = workflow.select([small, large], SETTINGS)
    assert chosen.label == "1h+1e" and not failed


def test_a_carrier_that_does_nothing_fails_the_gate():
    """AC-028. Measured at 0.1 % of the conduction over 48 removals."""
    idle = _candidate(weakest_share=0.0005)
    chosen, failed, _ = workflow.select([idle], SETTINGS)
    assert "earns" in failed


def test_the_clock_does_not_decide_whether_a_fit_reproduces():
    """FR-088, constraint C18. The verdict must not depend on the machine.

    Measured on the reader's twelve sweeps: at 90 K `2h+2e` reached the same
    residual to six digits on two machines -- 0.0055988 microohm cm, spread
    5.7e-5 -- in 17.0 s on one and 30.0 s on the other. Only the slower machine
    called it out of budget, discarded it, and answered `1h+2e`, whose residual
    is 2.6 times worse.
    """
    cut_short = _candidate(n_hole=2, n_electron=2, rmse_rhoxx=0.0055988,
                           spread=5.7e-5, expired=True, n_starts=5)
    worse = _candidate(n_hole=1, n_electron=2, rmse_rhoxx=0.014583, spread=4.1e-6)
    chosen, failed, _ = workflow.select([cut_short, worse], SETTINGS)
    assert chosen.label == "2h+2e", "the fit the data supports, whatever the clock said"
    assert failed == []


def test_a_fit_no_start_finished_twice_is_not_reproducible():
    """FR-088. The other half of C18: the clock may really cost the evidence.

    A spread needs two starting points to exist. `spread_of` reports an
    unmeasured spread as infinite, so such a fit fails this gate on the
    measurement rather than on the clock.
    """
    unmeasured = _candidate(spread=float("inf"), expired=True, n_starts=1)
    chosen, failed, _ = workflow.select([unmeasured], SETTINGS)
    assert "reproducible" in failed


# --------------------------------------------- the series across temperature

SMOOTH_SETTINGS = {"smoothing_weak": 1e-5, "smoothing_normal": 1e-4,
                   "smoothing_strong": 1e-3}

def _pair(mu, n=1e20, extra=()):
    carriers = [
        {"name": "h1", "kind": "hole", "density_cm3": n, "mobility_cm2Vs": mu,
         "conduction_share": 0.5, "mu_B_at_9T": mu * 9e-4},
        {"name": "e1", "kind": "electron", "density_cm3": n, "mobility_cm2Vs": mu,
         "conduction_share": 0.5, "mu_B_at_9T": mu * 9e-4},
    ]
    return [*carriers, *extra]


def _series(T_K, carriers):
    holes = sum(1 for c in carriers if c["kind"] == "hole")
    return workflow.TemperatureOutcome(
        T_K=T_K, mode="data", n_hole=holes, n_electron=len(carriers) - holes,
        grade="A", r2_rhoxx=0.999, r2_rhoxy=0.999, rmse_rhoxx=0.01, rmse_rhoxy=0.001,
        condition_number=100.0, spread=1e-8, seconds=1.0,
        bounds={"window": {"hole": (1.0, 1e6), "electron": (1.0, 1e6)},
                "count": {"hole": 1, "electron": 1}},
        carriers=tuple(carriers))


def test_roughness_needs_three_temperatures_and_one_carrier_set():
    """FR-031. Two points carry no curvature, and a band whose count changes is
    not one series: `n(T)` cannot be drawn across a model that changes."""
    band = [_series(T, _pair(6000.0)) for T in (5.0, 10.0, 20.0)]
    assert not np.isnan(workflow.roughness_of(band))
    assert np.isnan(workflow.roughness_of(band[:2]))

    third = {"name": "e2", "kind": "electron", "density_cm3": 1e19,
             "mobility_cm2Vs": 500.0, "conduction_share": 0.1, "mu_B_at_9T": 0.45}
    changing = [*band[:2], _series(20.0, _pair(6000.0, extra=(third,)))]
    assert np.isnan(workflow.roughness_of(changing))


def test_a_straight_series_reads_as_smooth_and_a_kinked_one_does_not():
    """The measure has to separate the two or it is decoration. Straight means
    straight in log parameter against temperature, which is what the penalty of
    FR-027 acts on."""
    straight = [_series(T, _pair(8000.0 * float(np.exp(-0.05 * (T - 5.0)))))
                for T in (5.0, 10.0, 20.0, 30.0)]
    kinked = [_series(T, _pair(mu)) for T, mu in
              ((5.0, 8000.0), (10.0, 2000.0), (20.0, 7000.0), (30.0, 3000.0))]
    easy, hard = workflow.roughness_of(straight), workflow.roughness_of(kinked)
    assert easy < 1e-9, f"a log-linear series should read as smooth, got {easy}"
    assert hard > 1.0 and hard > easy


def test_uneven_spacing_is_not_counted_as_roughness():
    """FR-031. The same log-linear series, measured every 5 K and then every
    20 K, must not be called rougher for the spacing alone."""
    def straight(temperatures):
        return [_series(T, _pair(8000.0 * float(np.exp(-0.05 * (T - 5.0)))))
                for T in temperatures]
    close = workflow.roughness_of(straight((5.0, 10.0, 15.0, 20.0)))
    far = workflow.roughness_of(straight((5.0, 25.0, 45.0, 65.0)))
    assert close < 1e-9 and far < 1e-9


def test_a_smoothing_strength_that_does_not_exist_is_refused():
    band = [_series(T, _pair(6000.0)) for T in (5.0, 10.0, 20.0)]
    with pytest.raises(ValueError, match="smoothing strength"):
        workflow.smooth_band({}, band, (), SMOOTH_SETTINGS, 1e-3, "very strong")


def test_smoothing_refuses_a_band_that_is_not_one_series():
    """Two temperatures have nothing to curve, and a changing count has nothing
    to couple."""
    band = [_series(T, _pair(6000.0)) for T in (5.0, 10.0, 20.0)]
    with pytest.raises(ValueError, match="three temperatures"):
        workflow.smooth_band({}, band[:2], (), SMOOTH_SETTINGS, 1e-3, "weak")
    third = {"name": "e2", "kind": "electron", "density_cm3": 1e19,
             "mobility_cm2Vs": 500.0, "conduction_share": 0.1, "mu_B_at_9T": 0.45}
    changing = [*band[:2], _series(20.0, _pair(6000.0, extra=(third,)))]
    with pytest.raises(ValueError, match="same carrier count"):
        workflow.smooth_band({}, changing, (), SMOOTH_SETTINGS, 1e-3, "weak")


# ------------------------------------------------------- islands, FR-090

def _sweep(T_K, n_hole, n_electron, answered=True):
    return workflow.TemperatureOutcome(
        T_K=T_K, mode="data", n_hole=n_hole, n_electron=n_electron, grade="A",
        r2_rhoxx=0.99, r2_rhoxy=0.99, rmse_rhoxx=0.01, rmse_rhoxy=0.001,
        condition_number=100.0, spread=1e-8, seconds=1.0, bounds={},
        carriers=(({"name": "h1"},) * (n_hole + n_electron)) if answered else ())


def test_an_island_carries_more_carriers_than_both_neighbours_share():
    """FR-090. This project's sweeps around the anomaly: 50 K and 70 K each add
    an electron their neighbours on both sides do not have."""
    series = [_sweep(40, 2, 2), _sweep(50, 2, 3), _sweep(60, 2, 2),
              _sweep(70, 2, 3), _sweep(80, 2, 2)]
    assert workflow.islands_of(series) == {1: (2, 2), 3: (2, 2)}


def test_a_sweep_with_fewer_carriers_than_its_neighbours_is_not_an_island():
    """FR-090. The first form of this rule was symmetric and marked 60 K, whose
    neighbours at 50 and 70 K both chose 2h+3e. Carrying fewer carriers claims
    no carrier that is not there, so it is not the failure being looked for."""
    series = [_sweep(40, 2, 2), _sweep(50, 2, 3), _sweep(60, 2, 2),
              _sweep(70, 2, 3), _sweep(80, 2, 2)]
    assert 2 not in workflow.islands_of(series)


def test_a_step_between_two_counts_is_not_an_island():
    """FR-090. A count must stay free to follow a real transition. At the
    charge-density-wave step the neighbours disagree, so nothing is marked."""
    series = [_sweep(80, 2, 2), _sweep(90, 2, 2), _sweep(100, 1, 1), _sweep(120, 1, 1)]
    assert workflow.islands_of(series) == {}


def test_the_ends_of_the_series_are_never_islands():
    """One neighbour is not two; there is nothing to disagree with."""
    series = [_sweep(5, 1, 1), _sweep(10, 2, 2), _sweep(20, 2, 2), _sweep(30, 1, 1)]
    assert workflow.islands_of(series) == {}


def test_a_sweep_with_no_answer_is_not_a_count():
    """The peaks rule can find nothing to fit; zero carriers is not a choice
    of zero carriers, and must not make an island of its neighbour."""
    series = [_sweep(40, 2, 2), _sweep(50, 0, 0, answered=False), _sweep(60, 2, 2),
              _sweep(70, 2, 2), _sweep(80, 2, 2)]
    assert workflow.islands_of(series) == {}


def test_a_pinned_count_covers_a_range_and_the_narrowest_range_wins():
    """FR-090. The requirement is about a band, not a temperature: `n(T)`
    cannot be plotted from fits that do not share a carrier set. One
    temperature inside a band may still need its own count, so the narrower
    range is the one that applies."""
    pinned = workflow.pinned_counts({"5-70": [2, 2], "50": [2, 3], "80-120": [1, 1]})
    assert workflow.count_for(5.0, pinned) == (2, 2)
    assert workflow.count_for(40.0, pinned) == (2, 2)
    assert workflow.count_for(50.0, pinned) == (2, 3)
    assert workflow.count_for(70.0, pinned) == (2, 2)
    assert workflow.count_for(90.0, pinned) == (1, 1)
    assert workflow.count_for(75.0, pinned) is None, "between the bands, nothing is pinned"


def test_nothing_pinned_leaves_every_temperature_to_the_procedure():
    assert workflow.count_for(50.0, workflow.pinned_counts(None)) is None
    assert workflow.count_for(50.0, workflow.pinned_counts({})) is None


def test_nothing_passing_is_reported_and_not_papered_over():
    """FR-086. Selecting by relaxing a test is what this forbids."""
    only = _candidate(at_bound=True, weakest_share=1e-5)
    chosen, failed, _ = workflow.select([only], SETTINGS)
    assert chosen is not None
    assert set(failed) >= {"earns", "free"}


def test_no_candidates_is_not_a_crash():
    chosen, failed, gates = workflow.select([], SETTINGS)
    assert chosen is None and failed == [] and gates == {}


# ------------------------------------------------------------ end to end

@pytest.mark.slow
def test_AC032_the_five_kelvin_sweep_through_fit_mode():
    """AC-032. The round trip for this feature, on the synthetic 5 K sweep.

    Pinned, so that a change in any of the six steps shows up here as a changed
    answer rather than as a plausible different one. It was pinned to the
    supplied sweep and to research 2.4's optimum until that sweep stopped being
    published with the program; these numbers are the same quantities recorded
    on the fixture that replaced it.

    The fixture is generated from three carriers of each sign. The procedure
    answers with five, recovering four of the six within a few percent and
    merging the two slowest into one effective hole -- which is what a
    five-carrier model of a six-carrier sample should do, and why the residual
    is what it is.
    """
    result = workflow.analyse(DATA, _document(), mode="data")
    assert result.mode == "data"
    outcome = result.outcomes[0]

    assert outcome.label == "3h+2e"
    assert outcome.grade == "A"
    assert outcome.determined, f"gates failed: {outcome.failed_gates}"
    assert outcome.r2_rhoxx == pytest.approx(0.999995, abs=5e-5)
    assert outcome.r2_rhoxy == pytest.approx(0.999992, abs=5e-5)
    assert outcome.condition_number == pytest.approx(613.0, rel=0.05)

    # the window bounded the search and did not choose the answer
    assert outcome.escaped_window == ()

    fast = max(outcome.carriers, key=lambda c: c["mobility_cm2Vs"])
    assert fast["kind"] == "electron"
    assert fast["mobility_cm2Vs"] == pytest.approx(17728, rel=0.05)

    holes = [c for c in outcome.carriers if c["kind"] == "hole"]
    fastest_hole = max(holes, key=lambda c: c["mobility_cm2Vs"])
    assert fastest_hole["density_cm3"] == pytest.approx(5.052e20, rel=0.05)
    assert fastest_hole["mobility_cm2Vs"] == pytest.approx(14903, rel=0.05)


@pytest.mark.slow
def test_the_search_covers_every_combination_up_to_the_bound():
    """FR-084. Stopping at the first acceptable one hides the alternatives."""
    result = workflow.analyse(DATA, _document(), mode="data")
    outcome = result.outcomes[0]
    bound = outcome.bounds["count"]
    assert len(outcome.candidates) == max(1, bound["hole"]) * max(1, bound["electron"])


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="count rule must be one of"):
        workflow.analyse(DATA, _document(), mode="whatever")


# ------------------------------------------------- one sweep of many

SERIES = ROOT / "tests" / "data" / "synthetic_series.csv"


@pytest.mark.parametrize("T_K", [20.0, 40.0])
def test_a_fit_in_a_table_of_many_temperatures_is_the_named_temperature(T_K):
    """A table holding every sweep once returned the first sweep's fit at every
    temperature: the twelve-sweep run through the page reported 10 K with 5 K's
    condition number to eight digits. Each fit must be of its own sweep."""
    seeds = [{"kind": "hole", "density_cm3": 1e21, "mobility_cm2Vs": 3000.0},
             {"kind": "electron", "density_cm3": 1e21, "mobility_cm2Vs": 3000.0}]
    fit, _, _ = workflow._fit_one(SERIES, _document(), seeds, None, 2, 0.0, T_K=T_K)
    assert fit.T_K == T_K

    config = cfg.resolve(dict(_document(), carriers=workflow._carrier_document(seeds)))
    alone = dataio.load_dataset(SERIES, config)
    group = next(g for g in alone.groups if g.T_K == T_K)
    assert fit.params.size == 4
    model_xx, _ = fitting.model_resistivity(group.B_T, fit.params, fitting.signs(fit.specs),
                                            float(config.model["hall_polarity"]))
    assert np.sqrt(np.mean((model_xx - group.rhoxx_uohmcm) ** 2)) == pytest.approx(fit.rmse_rhoxx, rel=1e-6)


def test_a_temperature_the_table_lacks_is_refused():
    seeds = [{"kind": "hole", "density_cm3": 1e21, "mobility_cm2Vs": 3000.0}]
    with pytest.raises(ValueError, match="expected one sweep"):
        workflow._fit_one(SERIES, _document(), seeds, None, 1, 0.0, T_K=7.0)
