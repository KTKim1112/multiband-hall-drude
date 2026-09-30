"""The mobility spectrum, end to end. Gates A to D.

Four questions, in the order that matters. A says whether this project's field
range can support the method at all; B says whether the separation works; C
says whether the Lorentzian order is a hidden knob; D says whether the
spectrum's proposal is a usable starting point for a fit.

Every synthetic carrier set here was chosen for this project. None is taken
from any published sample: the published method is borrowed, its numbers are
not, and a different crystal has no business being an expected value here.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, fitting, spectrum
from mbfit.core import separation
from mbfit.core import spectrum as core
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "configs" / "synthetic_5K.json"
# 121 points, not the 361 of a real sweep: the physics here is smooth and the
# extension is a nonlinear multistart fit, so the extra points buy nothing and
# cost four times the run. Measured: 5.5 s against 20.8 s for the same answer.
FIELDS = np.round(np.linspace(-9.0, 9.0, 121), 6)

# Three of each sign, arbitrary, chosen here.
SIX_DENSITY = [3.0e19, 6.0e20, 1.4e21, 8.0e19, 4.0e20, 1.6e21]
SIX_MOBILITY = [45000.0, 12000.0, 1500.0, 33000.0, 9000.0, 800.0]
SIX_SIGN = [SIGN_HOLE] * 3 + [SIGN_ELECTRON] * 3

# The noise floor research 002 section 2.3 measured on this project's sweeps.
REALISTIC_NOISE = 0.0005


def _sweep(density, mobility, sign, fields=FIELDS, noise=0.0, seed=0):
    xx, xy = resistivity(fields, density_to_si(density), mobility_to_si(mobility), sign)
    xx, xy = resistivity_from_si(xx), resistivity_from_si(xy)
    if noise:
        generator = np.random.default_rng(seed)
        xx = xx + generator.normal(scale=noise * np.abs(xx).mean(), size=fields.size)
        xy = xy + generator.normal(scale=noise * np.max(np.abs(xy)), size=fields.size)
    return dataio.TemperatureGroup(
        T_K=5.0, B_T=fields, rhoxx_uohmcm=xx, rhoxy_uohmcm=xy,
        in_fit_window=np.ones(fields.size, dtype=bool),
        n_records_dropped=0, n_mirror_interpolated=0, n_mirror_absent=0,
    )


def _config(**spectrum_settings):
    document = {
        "schema_version": "1.0",
        "columns": {"T": "T(K)", "B": "B(T)", "rhoxx": "a", "rhoxy": "b"},
        "carriers": [
            {"name": "h", "kind": "hole",
             "density": {"init": 1e21, "min": 1e15, "max": 1e23},
             "mobility": {"init": 2000.0, "min": 1.0, "max": 1e6}},
            {"name": "e", "kind": "electron",
             "density": {"init": 1e21, "min": 1e15, "max": 1e23},
             "mobility": {"init": 1000.0, "min": 1.0, "max": 1e6}},
        ],
        "optimization": {"multi_start": 4},
        "spectrum": dict(
            {"enabled": True, "lorentzian_terms": 6, "lorentzian_multi_start": 12},
            **spectrum_settings,
        ),
    }
    return cfg.resolve(document)


def _run(group, config):
    dataset = dataio.Dataset(groups=(group,), n_records_dropped=0)
    result = fitting.fit_dataset(dataset, config)
    return spectrum.for_temperature(result.fits[0], group, config)


def _matched(found, density, mobility, sign, kind):
    """Recovered carriers beside the true ones of that kind, fastest first."""
    truth = sorted(
        ((mobility[i], density[i]) for i in range(len(sign))
         if (sign[i] > 0) == (kind == "hole")),
        reverse=True,
    )
    return list(zip(truth, found))


# ============================================================ Gate B, first

@pytest.mark.slow
def test_GATEB_a_known_three_and_three_comes_back():
    """The separation works, and the spectrum reads the carriers off it.

    Noiseless, so this measures the method and not the measurement. Research
    003 section 4 records 1.9 % on mobility and 1.8 % on density.
    """
    entry = _run(_sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN), _config())

    assert entry.proposal == {"hole": 3, "electron": 3}
    assert not entry.ambiguous
    assert not entry.unresolved
    # Loose, and deliberately so. The extension is a multimodal nonlinear fit
    # and on noiseless data only about one start in twelve reaches the global
    # minimum, so its residual sits near 1e-5 rather than at machine
    # precision. What has to be tight is the answer, asserted below: the
    # separation and the inversion are forgiving of a 1e-5 extension and are
    # not forgiving of a broken one.
    assert entry.extension.max_relative_residual < 1e-3
    assert entry.recombination_error < 1e-12

    for kind in ("hole", "electron"):
        branch = entry.branch(kind)
        assert branch.negative_fraction == 0.0
        found = spectrum.carriers_from(branch, entry.sigma_xx_zero)
        for (true_mu, true_n), got in _matched(found, SIX_DENSITY, SIX_MOBILITY,
                                               SIX_SIGN, kind):
            assert got["mobility_cm2Vs"] == pytest.approx(true_mu, rel=0.05)
            assert got["density_cm3"] == pytest.approx(true_n, rel=0.05)


@pytest.mark.slow
def test_GATEB_it_survives_the_noise_this_project_actually_has():
    """Research 002 section 2.3 measured the floor at about 0.05 % of signal."""
    entry = _run(
        _sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN, noise=REALISTIC_NOISE),
        _config(),
    )
    assert entry.proposal == {"hole": 3, "electron": 3}
    assert not entry.ambiguous

    for kind in ("hole", "electron"):
        found = spectrum.carriers_from(entry.branch(kind), entry.sigma_xx_zero)
        for (true_mu, true_n), got in _matched(found, SIX_DENSITY, SIX_MOBILITY,
                                               SIX_SIGN, kind):
            assert got["mobility_cm2Vs"] == pytest.approx(true_mu, rel=0.10)
            assert got["density_cm3"] == pytest.approx(true_n, rel=0.10)


@pytest.mark.slow
def test_GATEB_the_count_does_not_move_with_the_regularisation():
    """The defect that caused this feature to be rewritten, as an assertion.

    The version before separation gave six peaks over nine decades and four
    over three on real data, so no count could be quoted. After separation
    each carrier type settles on one count across the whole range.
    """
    entry = _run(_sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN), _config())
    for kind in ("hole", "electron"):
        branch = entry.branch(kind)
        assert len(branch.plateaus) == 1, (kind, branch.plateaus)
        count, length = branch.plateaus[0]
        assert count == 3
        assert length == len(branch.steps)


# ============================================================== Gate A

@pytest.mark.slow
@pytest.mark.parametrize("slowest_mu_B", [2.0, 1.0, 0.5, 0.25])
def test_GATEA_where_the_slowest_carrier_stops_being_resolvable(slowest_mu_B):
    """This project has +/-9 T, so the limit is `mu B`, not the field range.

    Design measurement: a set spanning `mu B` of 27 down to 0.81 recovered as
    well at +/-9 T as at +/-18 T, because a fast carrier is already saturated
    at 9 T. What is *not* constrained is a carrier whose Lorentzian has not
    turned over. This walks the slowest carrier down and records where the
    recovery fails. The real sweeps sit at 0.96, 0.72 and 0.36.
    """
    slow_mu = slowest_mu_B / (9.0 * 1e-4)          # cm^2/Vs giving that mu*B at 9 T
    density = [5.0e20, 1.5e21, 4.0e20, 1.8e21]
    mobility = [30000.0, 2000.0, 25000.0, slow_mu]
    sign = [SIGN_HOLE, SIGN_HOLE, SIGN_ELECTRON, SIGN_ELECTRON]

    entry = _run(_sweep(density, mobility, sign), _config(lorentzian_terms=4))
    found = spectrum.carriers_from(entry.branch("electron"), entry.sigma_xx_zero)
    assert len(found) >= 1

    slowest = min(found, key=lambda item: item["mobility_cm2Vs"])
    error = abs(slowest["mobility_cm2Vs"] / slow_mu - 1.0)
    # Recorded rather than asserted tightly: the point of this gate is the
    # curve, and research 003 section 5 carries it. What is asserted is that
    # the method has not silently invented a carrier where none is resolvable.
    assert entry.branch("electron").negative_fraction < 0.5
    if slowest_mu_B >= 1.0:
        assert error < 0.15, f"mu*B = {slowest_mu_B}: mobility off by {error:.1%}"


# ============================================================== Gate C

@pytest.mark.slow
@pytest.mark.parametrize("n_terms", [5, 6, 7, 8])
def test_GATEC_the_lorentzian_order_is_a_declared_knob(n_terms):
    """The published method says the order carries no physical meaning.

    On this project's synthetic data it does, in one specific way: an order
    below the number of carriers cannot represent them and everything
    downstream fails. Research 003 section 6 records `n = 5` on six carriers
    giving a mobility wrong by a factor of seven. At or above the carrier
    count the answer settles, which is what this asserts.
    """
    entry = _run(_sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN), _config(lorentzian_terms=n_terms))
    found = spectrum.carriers_from(entry.branch("hole"), entry.sigma_xx_zero)

    if n_terms < 6:
        # Recorded, not required to fail: the gate exists to show the order
        # matters, and the requirement is that it be declared and recorded.
        assert entry.extension.max_relative_residual > 1e-3
        return

    assert entry.proposal["hole"] == 3
    for (true_mu, _), got in _matched(found, SIX_DENSITY, SIX_MOBILITY, SIX_SIGN, "hole"):
        assert got["mobility_cm2Vs"] == pytest.approx(true_mu, rel=0.10)


@pytest.mark.slow
def test_GATEC_an_order_below_the_carrier_count_is_visible_in_the_residual():
    """A reader must be able to see the failure without knowing the answer.

    The extension residual is the signal: it is at the noise when the order
    suffices and far above it when it does not. That is what makes the order
    a knob a reader can set rather than a trap.
    """
    too_few = _run(_sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN), _config(lorentzian_terms=4))
    enough = _run(_sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN), _config(lorentzian_terms=6))
    assert too_few.extension.max_relative_residual > 100 * enough.extension.max_relative_residual


@pytest.mark.slow
def test_GATEC_the_constraint_makes_the_answer_independent_of_the_start_count():
    """NR-011, and the reason it is the default. Research 003 section 3.1.

    In the free parameterisation two terms at nearly equal mobility can take
    large cancelling weights that leave the fit residual untouched and wreck
    the separation. Which basin the search finds then depends on how many
    starts it was given -- so the reported answer would move when a user
    changed a setting that has nothing to do with the physics. Article VII
    does not survive that.

    Read the agreement assertion below narrowly. Research 003 section 3.2.1
    measured the same statistic moving between `1` and `19` of 30 for the free
    form across noise draws that differ only in which random numbers were
    drawn, so it ranks nothing in general; on this one fixed draw and seed it
    comes out this way, and the test pins that because a change in it means a
    change in the search. What actually justifies NR-011 is structural and is
    asserted in the test below this one: under the constraint the separated
    parts cannot be negative at all, whatever basin is found.
    """
    group = _sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN, noise=REALISTIC_NOISE)

    free = _run(group, _config(lorentzian_terms=8, lorentzian_constrained=False))
    held = _run(group, _config(lorentzian_terms=8, lorentzian_constrained=True))

    # the fit quality does not tell them apart ...
    assert free.extension.max_relative_residual == pytest.approx(
        held.extension.max_relative_residual, rel=0.2)
    # ... but the reproducibility does
    assert held.extension.n_starts_agreeing > free.extension.n_starts_agreeing
    assert held.extension.constrained and not free.extension.constrained


@pytest.mark.slow
def test_the_constraint_makes_the_separated_parts_non_negative_by_construction():
    """NR-011. Not detected afterwards: impossible beforehand.

    `X^p = sum p_j/(1+mu_j^2 B^2)` with every `p_j >= 0` is a sum of positive
    terms at every field, measured or not. The check below is therefore not a
    measurement of luck but of whether the constraint is actually in force.
    """
    for n_terms in (4, 6, 8):
        entry = _run(
            _sweep(SIX_DENSITY, SIX_MOBILITY, SIX_SIGN, noise=REALISTIC_NOISE),
            _config(lorentzian_terms=n_terms),
        )
        assert np.all(entry.extension.weight_hole >= 0.0)
        assert np.all(entry.extension.weight_electron >= 0.0)
        for kind in ("hole", "electron"):
            assert entry.branch(kind).negative_fraction == 0.0, (n_terms, kind)


# ================================================== the real sweeps, and Gate D

@pytest.fixture(scope="module")
def real_5K():
    document = json.loads(REFERENCE.read_text(encoding="utf-8"))
    document["spectrum"] = {"enabled": True, "lorentzian_terms": 6,
                            "lorentzian_multi_start": 12}
    config = cfg.resolve(document)
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    return config, dataset, result, spectrum.estimate(result, dataset)[0]


@pytest.mark.slow
def test_the_real_sweep_settles_on_one_count_per_sign(real_5K):
    """What the unseparated version could not do. Research 003 section 7."""
    _, _, _, entry = real_5K
    for kind in ("hole", "electron"):
        branch = entry.branch(kind)
        assert len(branch.plateaus) == 1, (kind, branch.plateaus)
    assert not entry.ambiguous
    assert not entry.unresolved
    assert entry.recombination_error < 1e-12


@pytest.mark.slow
def test_the_separated_parts_of_the_real_sweep_keep_their_sign(real_5K):
    """If the extension failed, a separated conductivity would go negative."""
    _, _, _, entry = real_5K
    for kind in ("hole", "electron"):
        assert entry.branch(kind).negative_fraction < 0.01


@pytest.mark.slow
def test_GATED_the_proposal_is_a_usable_starting_point(real_5K):
    """FR-076. The spectrum proposes; a fit seeded there must be determined.

    An earlier attempt at more carriers, seeded by hand, reached a condition
    number of 1.3e10 and raised `D_NON_UNIQUE`. This asks whether seeding from
    the spectrum instead gives a problem the data can actually determine. The
    carrier count is still the reader's to declare -- what is tested is that
    the proposal, if accepted, is not immediately degenerate.
    """
    from mbfit import diagnostics

    _, _, _, entry = real_5K
    document = json.loads(REFERENCE.read_text(encoding="utf-8"))
    carriers = []
    for kind in ("hole", "electron"):
        for index, item in enumerate(
            spectrum.carriers_from(entry.branch(kind), entry.sigma_xx_zero), start=1
        ):
            carriers.append({
                "name": f"{kind[0]}{index}",
                "kind": kind,
                "density": {"init": item["density_cm3"], "min": 1e15, "max": 1e23},
                "mobility": {"init": item["mobility_cm2Vs"], "min": 1.0, "max": 1e6},
            })
    document["carriers"] = carriers
    document.setdefault("optimization", {})["multi_start"] = 8

    config = cfg.resolve(document)
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    fit = result.fits[0]
    codes = {e.code for e in diagnostics.collect(result, dataset)}

    assert fit.r2_rhoxx > 0.99
    # the number this gate exists for, recorded whatever it is
    assert np.isfinite(fit.condition_number)
    assert ("D_ILL_CONDITIONED" in codes) == (
        fit.condition_number > config.acceptance["condition_number_max"]
    )


# ------------------------------------------------------------------- plumbing

def test_the_feature_is_off_unless_asked_for():
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    assert spectrum.estimate(result, dataset) == ()


def test_the_grid_is_positive_and_ascending():
    grid = core.positive_grid(1e-2, 1e1, 20)
    assert np.all(grid > 0.0)
    assert np.all(np.diff(grid) > 0.0)


def test_a_signed_grid_is_refused_by_the_peak_reader():
    """The separation is upstream; a negative mobility here is a bug."""
    with pytest.raises(ValueError):
        core.peaks(np.array([-1.0, 1.0, 2.0]), np.array([1.0, 2.0, 1.0]), 0.02)


def test_peak_weights_partition_the_whole_spectrum():
    """FR-074: a density left outside a peak is a carrier density thrown away."""
    grid = np.logspace(2, 5, 200)
    density = sum(
        w * np.exp(-0.5 * ((np.log(grid) - np.log(c)) / 0.12) ** 2)
        for c, w in ((300.0, 1.0), (5000.0, 2.0), (40000.0, 0.5))
    )
    found = core.peaks(grid, density, 0.02)
    assert len(found) == 3
    assert sum(p["weight"] for p in found) == pytest.approx(float(density.sum()), rel=1e-12)


def test_plateaus_finds_runs_and_orders_them_by_length():
    assert core.plateaus([4, 4, 4, 4, 3, 2, 2, 2], 3) == [(4, 4), (2, 3)]
    assert core.plateaus([1, 2, 3, 4, 5, 6], 3) == []
    assert core.plateaus([4] * 12, 3) == [(4, 12)]
