"""FR-023 to FR-026 and the coupling in action. Gate 4.

Gate 4 has two halves. Gate 3 must still hold with every strategy selected in
turn, and the test that separates the two coupling orders must fail with
`order = 1` and pass with `order = 2`.

That second half was corrected before this file was written. It had been
attached to the spike-suppression test, which does not discriminate: a
first-order penalty suppresses an isolated excursion just as a second-order
one does. What separates them is a trend. Research 5.5 says second order
allows a smooth trend through unflattened while first order penalises the
trend itself, so the discriminating case is a parameter whose logarithm is
linear in temperature: the second-order penalty is then exactly zero at the
truth. Both tests are here; only the second carries the gate.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import fitting
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE
from mbfit.core.errors import MbfitError
from mbfit.dataio import Dataset, TemperatureGroup
from tests.test_roundtrip import TWO_BAND_SIGN, TWO_BAND_TRUE, carrier, make_config, make_group

FIELDS = np.linspace(-14.0, 14.0, 29)


def make_dataset(rows, sign, fields=FIELDS, corrupt=None, config=None):
    """`rows` is a mapping of temperature to true parameters.

    `config` applies the field window through the same function intake uses,
    so a test never carries its own copy of the rule.
    """
    from mbfit.dataio import field_window_mask

    groups = []
    for T_K, params in sorted(rows.items()):
        rho_xx, rho_xy = fitting.model_resistivity(fields, np.asarray(params, float), sign)
        if corrupt and T_K in corrupt:
            rho_xx = rho_xx * corrupt[T_K]
        groups.append(
            TemperatureGroup(
                T_K=float(T_K),
                B_T=fields,
                rhoxx_uohmcm=rho_xx,
                rhoxy_uohmcm=rho_xy,
                in_fit_window=(
                    np.ones(fields.shape, dtype=bool)
                    if config is None
                    else field_window_mask(fields, config)
                ),
                n_records_dropped=0,
                n_mirror_interpolated=0,
                n_mirror_absent=0,
            )
        )
    return Dataset(groups=tuple(groups), n_records_dropped=0)


ONE_CARRIER = [carrier("e1", "electron", n_init=5e18, mu_init=2000.0)]
TWO_CARRIER = [carrier("e1", "electron", mu_init=9000.0), carrier("h1", "hole", mu_init=3000.0)]


# ================================================ Gate 4, first half: FR-023 to 026

@pytest.mark.parametrize("strategy", ["independent", "sequential", "global_smooth"])
def test_gate3_still_holds_under_every_strategy(strategy):
    """AC-008 does not become negotiable because the temperatures were coupled."""
    truth = {5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE, 20.0: TWO_BAND_TRUE}
    dataset = make_dataset(truth, TWO_BAND_SIGN)
    config = make_config(
        TWO_CARRIER,
        optimization={"temperature_strategy": strategy, "multi_start": 6},
    )
    result = fitting.fit_dataset(dataset, config)
    assert result.strategy == strategy
    assert len(result.fits) == 3
    for fit in result.fits:
        worst = np.max(np.abs(fit.params_canonical / TWO_BAND_TRUE - 1.0))
        assert worst < 1e-5, f"{strategy} at {fit.T_K} K: {worst}"


def test_FR026_the_strategy_that_ran_is_recorded():
    dataset = make_dataset({5.0: [1e19, 5000.0]}, np.array([SIGN_ELECTRON]))
    for strategy in ("independent", "sequential", "global_smooth"):
        config = make_config(
            ONE_CARRIER, optimization={"temperature_strategy": strategy, "multi_start": 2}
        )
        assert fitting.fit_dataset(dataset, config).strategy == strategy


def test_FR024_sequential_seeding_is_observable():
    """The result at one temperature really does become the next start.

    With one start and an initial value far from the truth, the first
    temperature has to travel and the later ones do not.
    """
    truth = {5.0: [1e19, 5000.0], 10.0: [1e19, 5000.0], 20.0: [1e19, 5000.0]}
    dataset = make_dataset(truth, np.array([SIGN_ELECTRON]))
    far = [carrier("e1", "electron", n_init=1e22, mu_init=5.0)]
    config = make_config(far, optimization={"temperature_strategy": "sequential", "multi_start": 1})

    result = fitting.fit_dataset(dataset, config)
    for fit in result.fits:
        assert np.max(np.abs(fit.params / np.array([1e19, 5000.0]) - 1.0)) < 1e-6

    # The declared start is used only at the first temperature; the rest are
    # seeded, which is why start 0 of each later fit begins at the answer.
    first, second = result.fits[0], result.fits[1]
    assert second.starts[0].cost <= first.starts[0].cost + 1e-30


def test_sequential_and_independent_agree_where_the_data_is_clean():
    """Seeding changes where the search starts, not what it minimises."""
    truth = {5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE}
    dataset = make_dataset(truth, TWO_BAND_SIGN)
    answers = {}
    for strategy in ("independent", "sequential"):
        config = make_config(
            TWO_CARRIER, optimization={"temperature_strategy": strategy, "multi_start": 4}
        )
        answers[strategy] = fitting.fit_dataset(dataset, config).fits[0].params_canonical
    assert np.allclose(answers["independent"], answers["sequential"], rtol=1e-6)


# ============================================== the coupling suppresses a spike

SPIKE_TRUTH = {T: [1e19, 5000.0] for T in (5.0, 10.0, 20.0, 30.0, 40.0)}


def _mobility_deviation_at(result, T_K=20.0):
    """How far the corrupted temperature sits from the rest of the series."""
    values = {fit.T_K: fit.params[1] for fit in result.fits}
    others = [v for T, v in values.items() if T != T_K]
    return abs(values[T_K] / np.mean(others) - 1.0)


def test_an_isolated_excursion_is_suppressed_by_the_coupling():
    """One temperature whose longitudinal channel is 25 % wrong."""
    dataset = make_dataset(SPIKE_TRUTH, np.array([SIGN_ELECTRON]), corrupt={20.0: 1.25})

    alone = fitting.fit_dataset(
        dataset,
        make_config(ONE_CARRIER, optimization={"temperature_strategy": "independent",
                                               "multi_start": 3}),
    )
    coupled = fitting.fit_dataset(
        dataset,
        make_config(
            ONE_CARRIER,
            optimization={"temperature_strategy": "global_smooth", "multi_start": 3},
            smoothing={"enabled": True, "order": 2, "lambda_mobility": 200.0},
        ),
    )
    assert _mobility_deviation_at(alone) > 0.15
    assert _mobility_deviation_at(coupled) < _mobility_deviation_at(alone) / 2.0


def test_both_orders_suppress_the_excursion_which_is_why_it_cannot_be_the_gate():
    """Recorded so the corrected Gate 4 wording is checkable, not asserted."""
    dataset = make_dataset(SPIKE_TRUTH, np.array([SIGN_ELECTRON]), corrupt={20.0: 1.25})
    alone = fitting.fit_dataset(
        dataset,
        make_config(ONE_CARRIER, optimization={"temperature_strategy": "independent",
                                               "multi_start": 3}),
    )
    for order in (1, 2):
        coupled = fitting.fit_dataset(
            dataset,
            make_config(
                ONE_CARRIER,
                optimization={"temperature_strategy": "global_smooth", "multi_start": 3},
                smoothing={"enabled": True, "order": order, "lambda_mobility": 200.0},
            ),
        )
        assert _mobility_deviation_at(coupled) < _mobility_deviation_at(alone)


# ================================ Gate 4, second half: what separates the orders

TREND_TEMPERATURES = np.arange(5.0, 51.0, 5.0)
TREND_RATE = 2.0 / 45.0          # log n rises by 2 across the series


def _trend_dataset():
    rows = {
        float(T): [1e19 * np.exp(TREND_RATE * (T - 5.0)), 5000.0]
        for T in TREND_TEMPERATURES
    }
    return make_dataset(rows, np.array([SIGN_ELECTRON])), rows


def _recovered_rate(result):
    T = np.array([fit.T_K for fit in result.fits])
    log_n = np.log([fit.params[0] for fit in result.fits])
    return float(np.polyfit(T, log_n, 1)[0])


@pytest.mark.parametrize("order,keeps_the_trend", [(1, False), (2, True)])
def test_the_case_that_separates_first_from_second_order(order, keeps_the_trend):
    """A parameter whose logarithm is linear in temperature.

    Second order penalises curvature, and a straight line has none, so the
    penalty is exactly zero at the truth and the trend passes untouched.
    First order penalises the trend itself and flattens it. This is the test
    Gate 4 hangs on.
    """
    dataset, _ = _trend_dataset()
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=5000.0)],
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2},
        smoothing={"enabled": True, "order": order, "lambda_density": 200.0},
    )
    recovered = _recovered_rate(fitting.fit_dataset(dataset, config))
    kept = recovered / TREND_RATE

    if keeps_the_trend:
        assert kept == pytest.approx(1.0, abs=0.02)
    else:
        assert kept < 0.9


def test_without_any_coupling_both_orders_are_irrelevant_and_the_trend_is_exact():
    dataset, _ = _trend_dataset()
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=5000.0)],
        optimization={"temperature_strategy": "independent", "multi_start": 2},
    )
    assert _recovered_rate(fitting.fit_dataset(dataset, config)) == pytest.approx(
        TREND_RATE, rel=1e-6
    )


# ================================================================== FR-053

def test_FR053_a_break_lets_the_two_sides_disagree():
    """A step in the middle of the series, with and without a break at it."""
    rows = {5.0: [1e19, 5000.0], 10.0: [1e19, 5000.0],
            30.0: [3e19, 5000.0], 35.0: [3e19, 5000.0]}
    dataset = make_dataset(rows, np.array([SIGN_ELECTRON]))
    common = dict(
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2},
    )
    spanning = fitting.fit_dataset(
        dataset,
        make_config([carrier("e1", "electron", n_init=1.5e19)], **common,
                    smoothing={"enabled": True, "order": 1, "lambda_density": 300.0}),
    )
    cut = fitting.fit_dataset(
        dataset,
        make_config([carrier("e1", "electron", n_init=1.5e19)], **common,
                    smoothing={"enabled": True, "order": 1, "lambda_density": 300.0,
                               "breaks_K": [20.0]}),
    )

    def step(result):
        n = [fit.params[0] for fit in result.fits]
        return (n[2] + n[3]) / (n[0] + n[1])

    assert step(cut) > step(spanning)
    assert step(cut) == pytest.approx(3.0, rel=0.05)


def test_E_CONFIG_BREAK_OUTSIDE_RANGE_reaches_the_user_through_fit_dataset():
    dataset = make_dataset({5.0: [1e19, 5000.0], 10.0: [1e19, 5000.0]},
                           np.array([SIGN_ELECTRON]))
    config = make_config(
        ONE_CARRIER,
        optimization={"temperature_strategy": "global_smooth", "multi_start": 1},
        smoothing={"enabled": True, "breaks_K": [90.0]},
    )
    with pytest.raises(MbfitError, match="E_CONFIG_BREAK_OUTSIDE_RANGE"):
        fitting.fit_dataset(dataset, config)


# ================================================================== FR-032

def test_FR032_the_monotonic_prior_bends_a_series_and_can_be_overcome():
    """A soft prior: it costs, and a firm enough data set pays the cost."""
    rows = {5.0: [3e19, 5000.0], 20.0: [2e19, 5000.0], 40.0: [1e19, 5000.0]}
    dataset = make_dataset(rows, np.array([SIGN_ELECTRON]))
    declared = [dict(carrier("e1", "electron", n_init=2e19), monotonic_density="increase")]

    gentle = fitting.fit_dataset(
        dataset,
        make_config(declared,
                    optimization={"temperature_strategy": "global_smooth", "multi_start": 2},
                    monotonic_penalty={"enabled": True, "lambda": 1e-3}),
    )
    firm = fitting.fit_dataset(
        dataset,
        make_config(declared,
                    optimization={"temperature_strategy": "global_smooth", "multi_start": 2},
                    monotonic_penalty={"enabled": True, "lambda": 5e3}),
    )

    def total_fall(result):
        n = [fit.params[0] for fit in result.fits]
        return np.log(n[0]) - np.log(n[-1])

    # The data says the density falls. A weak prior loses; a strong one bends
    # the answer, which is exactly why ledger C4 keeps it off by default.
    assert total_fall(gentle) == pytest.approx(np.log(3.0), rel=0.02)
    assert total_fall(firm) < total_fall(gentle)


# ================================================================== FR-047

def test_order_changes_are_carried_on_the_result():
    """Two same-sign carriers whose mobilities cross partway up the series."""
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    rows = {
        5.0: [1e19, 9000.0, 1e20, 400.0],
        10.0: [1e19, 9000.0, 1e20, 400.0],
        20.0: [1e19, 300.0, 1e20, 9000.0],
    }
    dataset = make_dataset(rows, sign)
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=5000.0),
         carrier("e2", "electron", n_init=1e20, mu_init=1000.0)],
        optimization={"temperature_strategy": "independent", "multi_start": 8},
    )
    result = fitting.fit_dataset(dataset, config)
    assert isinstance(result.order_changes, tuple)


def test_the_global_problem_reports_its_own_conditioning():
    dataset = make_dataset({5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    config = make_config(
        TWO_CARRIER, optimization={"temperature_strategy": "global_smooth", "multi_start": 2}
    )
    result = fitting.fit_dataset(dataset, config)
    assert result.global_condition_number is not None
    assert result.global_condition_number > 0.0
    for fit in result.fits:
        assert fit.condition_number > 0.0


# ------------------------------------ the band as one call: AC-039, AC-040

#: Five temperatures, so the second-order coupling has three interior knots.
BAND_TEMPERATURES = len(SPIKE_TRUTH)


def _band():
    return make_dataset(SPIKE_TRUTH, np.array([SIGN_ELECTRON]))


def _coupled_config(**optimization):
    return make_config(
        ONE_CARRIER,
        optimization={"temperature_strategy": "global_smooth", **optimization},
        smoothing={"enabled": True, "order": 2, "lambda_mobility": 200.0},
    )


def test_a_coupled_fit_is_bounded_by_its_own_budget():
    """AC-039. The whole band is one call to the optimiser, so the clock has to
    be read inside the residual; a check between starts bounds nothing.

    Research 005 section 6: one such call ran 3061 s while the page showed a
    progress line that never moved and a stop button that did nothing.
    """
    with pytest.raises(MbfitError) as raised:
        fitting.fit_dataset(_band(), _coupled_config(multi_start=2, global_budget_s=1e-6))
    assert raised.value.code == "E_FIT_NO_START"
    # and it says which of the two things went wrong
    assert raised.value.detail["n_expired"] == 2


def test_the_budget_of_one_sweep_is_not_the_budget_of_a_whole_band():
    """AC-039 is its own setting. `fit_budget_s` is thirty seconds and bounds a
    sweep; a band of thirteen is 104 parameters against eight, so reusing it
    would expire every start of every band worth coupling."""
    run = fitting.fit_dataset(
        _band(), _coupled_config(multi_start=1, fit_budget_s=1e-6))
    assert len(run.fits) == BAND_TEMPERATURES, (
        "the sweep budget must not reach the coupled fit")

def test_a_coupled_fit_stops_while_it_is_fitting_not_between_starts():
    """FR-098. The band is one call to the optimiser, so a stop consulted only
    between starts leaves the request unanswered for as long as that call runs
    -- 3061 s, measured (research 005 section 6).

    The stop here becomes true only once the fit is under way, and there is one
    start, so nothing but a check inside the residual can answer it. A stop
    checked only between starts lets this fit run to the end.
    """
    inside = {"yet": False}

    def watch(**event):
        if "evaluations" in event:
            inside["yet"] = True

    with pytest.raises(fitting.FitStopped):
        fitting.fit_dataset(_band(), _coupled_config(multi_start=1),
                            progress=watch, stop=lambda: inside["yet"])


def test_a_coupled_fit_says_what_it_is_doing():
    """FR-097. Elapsed against the budget is the only honest denominator: a
    least-squares run has no known total."""
    seen = []
    fitting.fit_dataset(_band(), _coupled_config(multi_start=2),
                        progress=lambda **event: seen.append(event))
    assert any("start" in event for event in seen), "no start was announced"
    assert any("evaluations" in event for event in seen), "no work was reported"
    reported = [event for event in seen if "start" in event]
    assert [event["start"] for event in reported] == [0, 1]
    assert all(event["starts"] == 2 for event in reported)


def test_a_coupled_refit_of_a_pinned_band_takes_one_start():
    """AC-040. `smooth_band` seeds every temperature at the answer the pinned
    refit already found, so the coupled fit refines an answer in hand. Starts
    drawn at random around it re-solve a solved problem, and eight of them were
    three hours against twenty-five minutes on a band of thirteen."""
    assert cfg.DEFAULTS["workflow"]["smooth_multi_start"] == 1
