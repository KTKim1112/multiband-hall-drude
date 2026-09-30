"""The three-temperature series, and what coupling does to it. Research 5.6.

The sample was measured at 5, 20 and 40 K and crosses its Hall sign change
between the last two. That makes the series the first real test of the
temperature strategies of FR-023 to FR-025, and it settles three things that
were previously only reasoned about:

    sequential is a no-op when every temperature already converges
    a break in the only interior gap switches a second-order penalty off
    coupling three temperatures drags the good ones rather than lifting the bad

The last is why `smoothing.enabled` keeps its default of false.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting
from mbfit.core import penalties

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERIES = ROOT / "tests" / "data" / "synthetic_series.csv"
CONFIG = ROOT / "configs" / "synthetic_5K.json"

TEMPERATURES = (5.0, 20.0, 40.0)


def _document(**overrides):
    doc = json.loads(CONFIG.read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(doc.get(key), dict):
            doc[key] = dict(doc[key], **value)
        else:
            doc[key] = value
    return doc


def test_a_stop_is_answered_between_temperatures():
    """FR-098, AC-033. A strategy that fits one temperature at a time has to
    be stoppable between them.

    These two took no stop at all. A stop pressed during the preparatory fit of
    an analysis therefore went unanswered until every sweep had been fitted --
    minutes on a table of twelve, against the thirty-five seconds AC-033
    allows, and the work went on holding the machine the whole time.
    """
    config = cfg.resolve(_document())
    dataset = dataio.load_dataset(SERIES, config)
    assert len(dataset.groups) == 3, "the stop has to have somewhere to land"

    for strategy in (fitting.fit_independent, fitting.fit_sequential):
        asked = []

        def stop(_asked=asked):
            _asked.append(len(_asked))
            return len(_asked) > 1          # the first through, the second not

        with pytest.raises(fitting.FitStopped):
            strategy(dataset, config, stop=stop)
        assert len(asked) == 2, f"{strategy.__name__} fitted past the stop"


def _run(**overrides):
    config = cfg.resolve(_document(**overrides))
    dataset = dataio.load_dataset(SERIES, config)
    result = fitting.fit_dataset(dataset, config)
    return result, dataset


@pytest.fixture(scope="module")
def independent():
    return _run()


def test_the_series_is_the_three_sweeps(independent):
    result, dataset = independent
    assert dataset.temperatures == TEMPERATURES
    assert all(group.n_records == 361 for group in dataset.groups)


# ------------------------------------------------------------- FR-024 is a no-op

def test_sequential_reaches_the_same_optimum(independent):
    """Seeding changes where the search starts, not what it minimises.

    Research 5.6. The first temperature is bit-identical because it has
    nothing to be seeded from. The seeded ones land on the same cost to
    twelve digits while their parameters differ at the 1e-7 level, which is
    the flatness of the basin and not a different answer.
    """
    reference, _ = independent
    sequential, _ = _run(optimization={"temperature_strategy": "sequential"})

    first_a, first_b = reference.fits[0], sequential.fits[0]
    assert np.array_equal(first_a.params_canonical, first_b.params_canonical)

    for a, b in zip(reference.fits, sequential.fits):
        assert a.T_K == b.T_K
        cost_a = min(s.cost for s in a.starts)
        cost_b = min(s.cost for s in b.starts)
        assert cost_b == pytest.approx(cost_a, rel=1e-10)
        assert np.allclose(b.params_canonical, a.params_canonical, rtol=1e-6)


def test_the_seeded_difference_tracks_the_conditioning(independent):
    """Equal cost, different parameters -- by how much the basin is flat.

    Research 5.6 measures the seeded difference at two sweeps whose kappa
    differs by more than an order of magnitude, and it rises with kappa; the
    numbers are there. The ill-conditioned temperature is the one whose
    answer is least pinned down at equal cost, which is the same statement
    AC-010 makes and a second way of seeing it.
    """
    reference, _ = independent
    sequential, _ = _run(optimization={"temperature_strategy": "sequential"})

    spread = {}
    for a, b in zip(reference.fits, sequential.fits):
        spread[a.T_K] = float(np.max(np.abs(b.params_canonical / a.params_canonical - 1.0)))

    assert spread[5.0] == 0.0
    assert spread[40.0] > spread[20.0]
    assert reference.fits[2].condition_number > reference.fits[1].condition_number


# ------------------------------------------- the jump is real, and it is reported

def test_exactly_one_jump_and_it_is_not_a_relabelling(independent):
    """AC-004 calibrated: quiet from 5 to 20 K, loud across the sign change.

    Research 7, Q1. On a sample's series the worst parameter ratio across the
    first gap was under 5 and across the second well over it, so a threshold
    of 5 separates an ordinary temperature dependence from a change of regime;
    the two ratios are in that record. FR-047 must agree that
    it is a real jump: a label exchange is free under PM-003 and would make
    the same diagnostic meaningless.
    """
    result, dataset = independent
    jumps = [e for e in diagnostics.collect(result, dataset) if e.code == "D_JUMP"]

    assert len(jumps) == 1
    entry = jumps[0]
    assert (entry.where["T_K"], entry.where["next_T_K"]) == (20.0, 40.0)
    assert entry.where["quantity"] == "density"
    assert entry.measured == pytest.approx(7.04, abs=0.2)

    assert result.order_changes == ()
    assert not any(e.code == "D_LABEL_SWAP" for e in diagnostics.collect(result, dataset))


def test_the_sign_change_is_in_the_data_not_only_in_the_fit(independent):
    """Low-field Hall slope: +0.0282, +0.0111, -0.0705 micro-ohm cm / T.

    Under PM-001 that makes the 40 K sweep electron dominated where the other
    two are hole dominated, which is the physical reason the parameters are
    not a continuous family and must not be smoothed into one.

    The supplied sweeps this fixture replaces gave the same three signs in the
    same order, which is what the test is about; their slopes are in the
    research record and are not published with the program.
    """
    _, dataset = independent
    slopes = []
    for group in dataset.groups:
        low = np.abs(group.B_T) <= 1.0
        slopes.append(np.polyfit(group.B_T[low], group.rhoxy_uohmcm[low], 1)[0])
    assert slopes[0] == pytest.approx(0.0282, abs=0.002)
    assert slopes[1] == pytest.approx(0.0111, abs=0.002)
    assert slopes[2] == pytest.approx(-0.0705, abs=0.002)
    assert slopes[0] > slopes[1] > 0.0 > slopes[2]


# --------------------------------------------------- why coupling stays switched off

def test_a_break_in_the_only_interior_gap_removes_the_penalty_entirely():
    """Second order needs three points in a segment. Research 5.6.

    A break anywhere between 20 and 40 K leaves segments of two and one, so
    the penalty has nothing to form a curvature from. Declaring the break and
    leaving coupling off are then the same computation, which is why there is
    nothing to choose here.
    """
    # The four strongest carriers the fixture is generated from, at its three
    # temperatures (tests/data/make_synthetic.py). Only the shape reaches the
    # assertions -- what is checked is how many residual rows a break leaves,
    # not what they contain -- so any series of the right shape would do, and
    # invented numbers are used rather than a sample's.
    sign = np.array([1.0, 1.0, -1.0, -1.0])
    X = np.log(np.array([
        [5.0e20, 15000.0, 1.1e21, 2300.0, 4.0e20, 18000.0, 1.0e21, 1900.0],
        [5.0e20, 9000.0, 9.5e20, 1400.0, 4.2e20, 10000.0, 9.5e20, 1230.0],
        [7.5e20, 3500.0, 1.2e21, 600.0, 8.0e20, 4800.0, 1.2e21, 3200.0],
    ]))
    T = np.array(TEMPERATURES)

    unbroken = penalties.coupling_residual(
        X, T, sign, order=2, lambda_density=1.0, lambda_mobility=1.0)
    broken = penalties.coupling_residual(
        X, T, sign, order=2, lambda_density=1.0, lambda_mobility=1.0, breaks=(29.0,))

    assert unbroken.size == 8          # one interior node, one row per parameter
    assert broken.size == 0
    # first order survives the break, because it needs only two points
    first = penalties.coupling_residual(
        X, T, sign, order=1, lambda_density=1.0, lambda_mobility=1.0, breaks=(29.0,))
    assert first.size == 8


def test_coupling_drags_the_well_conditioned_temperatures(independent):
    """The measurement behind leaving `smoothing.enabled` false. Research 5.6.

    At a coupling strong enough to matter, the 5 K sweep -- which needs no
    help, and whose accuracy research 4.8 bounds -- moves by more
    than that, and the 40 K fit it was supposed to rescue gets worse rather
    than better.
    """
    reference, _ = independent
    coupled, _ = _run(
        optimization={"temperature_strategy": "global_smooth"},
        smoothing={"enabled": True, "order": 2,
                   "lambda_density": 1.0, "lambda_mobility": 1.0},
    )

    before = np.array([f.params_canonical for f in reference.fits])
    after = np.array([f.params_canonical for f in coupled.fits])
    moved = np.abs(after / before - 1.0).max(axis=1)

    assert moved[0] > 0.15, f"5 K moved by only {moved[0]:.3f}"
    assert moved[2] > 0.40, f"40 K moved by only {moved[2]:.3f}"
    assert coupled.fits[2].r2_rhoxx < reference.fits[2].r2_rhoxx

    # and the conditioning it did improve is a global quantity, not a rescue
    # of the temperature that needed one
    assert coupled.global_condition_number is not None
    assert coupled.global_condition_number < 2400.0
