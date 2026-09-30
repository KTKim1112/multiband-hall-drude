"""AC-008, the round trip. Gate 3.

Data is generated from parameters that are *known*, put through the program,
and the original values must come back out.

This is the decisive test of the project. A factor of two, a flipped sign or
a lost unit conversion does not crash anything, does not lower R-squared and
is not visible in any residual; it returns a plausible number. No amount of
reading, reviewing or type-checking catches that. Only a round trip through a
known answer does. Nothing in Phases 4 to 7 was begun before this passed.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import fitting
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE
from mbfit.core.errors import MbfitError
from mbfit.dataio import TemperatureGroup

COLUMNS = {"T": "T(K)", "B": "B(T)", "rhoxx": "rxx", "rhoxy": "rxy"}

# Two carriers of comparable, high mobility. Research 4.2 measured this case
# recovering to 0.18 % at 14 T with 0.1 % noise.
TWO_BAND_TRUE = np.array([3.0e18, 12000.0, 1.1e19, 3500.0])
TWO_BAND_SIGN = np.array([SIGN_ELECTRON, SIGN_HOLE])


def carrier(name, kind, n_init=1e19, mu_init=5000.0, n_min=1e14, n_max=1e24, mu_min=1.0, mu_max=1e6):
    return {
        "name": name,
        "kind": kind,
        "density": {"init": n_init, "min": n_min, "max": n_max},
        "mobility": {"init": mu_init, "min": mu_min, "max": mu_max},
    }


def make_config(carriers, **sections):
    document = {
        "schema_version": "1.0",
        "columns": COLUMNS,
        "carriers": carriers,
    }
    document.update(sections)
    return cfg.resolve(document)


def make_group(true_params, sign, fields=None, hall_polarity=1.0, noise=0.0, seed=0, T_K=5.0):
    """A synthetic sweep from parameters that are known."""
    B = np.linspace(-14.0, 14.0, 57) if fields is None else np.asarray(fields, dtype=float)
    rho_xx, rho_xy = fitting.model_resistivity(B, true_params, sign, hall_polarity)
    if noise:
        generator = np.random.default_rng(seed)
        rho_xx = rho_xx * (1.0 + noise * generator.normal(size=B.size))
        rho_xy = rho_xy + noise * np.max(np.abs(rho_xy)) * generator.normal(size=B.size)
    return TemperatureGroup(
        T_K=T_K,
        B_T=B,
        rhoxx_uohmcm=rho_xx,
        rhoxy_uohmcm=rho_xy,
        in_fit_window=np.ones(B.shape, dtype=bool),
        n_records_dropped=0,
        n_mirror_interpolated=0,
        n_mirror_absent=0,
    )


def worst_relative(recovered, truth):
    recovered = np.asarray(recovered, dtype=float)
    truth = np.asarray(truth, dtype=float)
    return float(np.max(np.abs(recovered / truth - 1.0)))


# ============================================================== AC-008 itself

@pytest.mark.parametrize("kind,sign", [("electron", SIGN_ELECTRON), ("hole", SIGN_HOLE)])
def test_AC008_one_carrier_returns_the_values_it_was_generated_from(kind, sign):
    """The non-negotiable one. Relative 1e-6."""
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([sign]))
    config = make_config([carrier("c1", kind, n_init=5e18, mu_init=2000.0)],
                         optimization={"multi_start": 4})

    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params, truth) < 1e-6


def test_AC008_holds_from_a_starting_point_three_decades_away():
    """Recovery must not depend on being handed the answer."""
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]))
    config = make_config([carrier("e1", "electron", n_init=1e22, mu_init=5.0)],
                         optimization={"multi_start": 6})
    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params, truth) < 1e-6


def test_two_carriers_recover_to_the_tolerance_research_measured():
    """Noiseless, so the recovery is far better than the 0.18 % of research 4.2."""
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN)
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=6000.0),
         carrier("h1", "hole", n_init=1e19, mu_init=6000.0)],
        optimization={"multi_start": 8},
    )
    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params_canonical, TWO_BAND_TRUE) < 1e-6


def test_two_carriers_with_realistic_noise_match_the_measured_figure():
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN, noise=0.001, seed=1)
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=6000.0),
         carrier("h1", "hole", n_init=1e19, mu_init=6000.0)],
        optimization={"multi_start": 8},
    )
    result = fitting.fit_temperature(group, config)
    # Research 4.2: 0.18 % worst at 14 T with 0.1 % noise. Allow a factor of
    # ten so the test is not a thermometer for the random draw.
    assert worst_relative(result.params_canonical, TWO_BAND_TRUE) < 0.02


def test_the_hall_sign_survives_the_round_trip():
    """PM-001 through the whole machine, not only through drude.py.

    Data generated from an electron must come back as an electron: fitting it
    with the carrier declared a hole cannot reach the same curves.
    """
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]))

    right = fitting.fit_temperature(
        group, make_config([carrier("e1", "electron")], optimization={"multi_start": 4})
    )
    wrong = fitting.fit_temperature(
        group, make_config([carrier("h1", "hole")], optimization={"multi_start": 4})
    )
    assert right.starts[0].cost < 1e-20
    assert wrong.starts[0].cost > 1e-6


def test_a_reversed_polarity_round_trips_when_it_is_declared():
    """PM-002: data taken with the opposite wiring, fitted with it declared."""
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]), hall_polarity=-1.0)
    config = make_config(
        [carrier("e1", "electron")],
        model={"hall_polarity": -1},
        optimization={"multi_start": 4},
    )
    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params, truth) < 1e-6


# ================================================== what the objective offers

@pytest.mark.parametrize("fit_mode", ["both", "rhoxx", "rhoxy"])
def test_FR018_every_fit_mode_runs_and_the_full_one_is_the_best_determined(fit_mode):
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN)
    config = make_config(
        [carrier("e1", "electron", mu_init=9000.0), carrier("h1", "hole", mu_init=3000.0)],
        optimization={"fit_mode": fit_mode, "multi_start": 6},
    )
    result = fitting.fit_temperature(group, config)
    assert np.all(np.isfinite(result.params))
    if fit_mode == "both":
        assert worst_relative(result.params_canonical, TWO_BAND_TRUE) < 1e-6


@pytest.mark.parametrize("fit_space", ["rho", "sigma"])
def test_FR019_both_spaces_reach_the_same_answer_on_clean_data(fit_space):
    """They are the same information, so they must agree where there is no noise."""
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN)
    config = make_config(
        [carrier("e1", "electron", mu_init=9000.0), carrier("h1", "hole", mu_init=3000.0)],
        optimization={"fit_space": fit_space, "multi_start": 6},
    )
    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params_canonical, TWO_BAND_TRUE) < 1e-5


def test_FR020_the_scales_actually_applied_are_recorded():
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN)
    config = make_config([carrier("e1", "electron"), carrier("h1", "hole")],
                         optimization={"multi_start": 2})
    result = fitting.fit_temperature(group, config)
    assert result.channel_scales[0] > 0.0 and result.channel_scales[1] > 0.0


def test_FR022_low_field_emphasis_changes_the_objective_and_nothing_else():
    from mbfit.core.residual import low_field_weight

    B = np.array([0.0, 0.5, 1.0, 5.0, 9.0])
    off = low_field_weight(B, False, 5.0, 1.0)
    on = low_field_weight(B, True, 5.0, 1.0)
    assert np.allclose(off, 1.0)
    assert on[0] == pytest.approx(6.0)          # 1 + alpha at zero field
    assert on[-1] == pytest.approx(1.0, abs=1e-12)  # and nothing at high field
    assert np.all(np.diff(on) < 0.0)


# ================================================== the search and its record

def test_FR036_every_start_is_kept_not_only_the_best():
    """FR-045 has nothing to compare against otherwise."""
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN, noise=0.002, seed=3)
    config = make_config([carrier("e1", "electron"), carrier("h1", "hole")],
                         optimization={"multi_start": 7})
    result = fitting.fit_temperature(group, config)
    assert len(result.starts) == 7
    assert [s.start_index for s in result.starts] == list(range(7))
    # The retained answer is the best of them, and the rest are still there.
    cheapest = min(result.starts, key=lambda s: s.cost)
    assert np.allclose(result.params, cheapest.params, rtol=1e-9)
    assert len({round(s.cost, 12) for s in result.starts}) >= 1


def test_NR005_the_same_configuration_gives_identical_numbers():
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN, noise=0.002, seed=4)
    config = make_config([carrier("e1", "electron"), carrier("h1", "hole")],
                         optimization={"multi_start": 5, "random_seed": 99})
    first = fitting.fit_temperature(group, config)
    second = fitting.fit_temperature(group, config)
    assert np.array_equal(first.params, second.params)
    assert [s.cost for s in first.starts] == [s.cost for s in second.starts]
    assert first.seed == second.seed


def test_the_seed_is_recorded_and_keyed_on_the_temperature():
    """Article VII, and a property worth having: adding a temperature to a
    series must not change the starting points chosen for the others."""
    config = make_config([carrier("e1", "electron")], optimization={"random_seed": 7})
    at_five = fitting.fit_temperature(make_group(np.array([1e19, 5000.0]),
                                                 np.array([SIGN_ELECTRON]), T_K=5.0), config)
    at_ten = fitting.fit_temperature(make_group(np.array([1e19, 5000.0]),
                                                np.array([SIGN_ELECTRON]), T_K=10.0), config)
    assert at_five.seed != at_ten.seed
    again = fitting.fit_temperature(make_group(np.array([1e19, 5000.0]),
                                               np.array([SIGN_ELECTRON]), T_K=5.0), config)
    assert again.seed == at_five.seed


def test_E_FIT_NO_START_when_every_start_fails(monkeypatch):
    def always_fails(*args, **kwargs):
        raise ValueError("planted")

    monkeypatch.setattr(fitting, "least_squares", always_fails)
    group = make_group(np.array([1e19, 5000.0]), np.array([SIGN_ELECTRON]))
    config = make_config([carrier("e1", "electron")], optimization={"multi_start": 3})
    with pytest.raises(MbfitError, match="E_FIT_NO_START"):
        fitting.fit_temperature(group, config)


# ============================================================ bounds, NR-006

def test_TC004_a_truth_outside_the_bounds_returns_the_boundary_exactly():
    """NR-006: the reported value is the bound, not a neighbour of it."""
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]))
    squeezed = carrier("e1", "electron", n_init=2e20, mu_init=5000.0,
                       n_min=1e20, n_max=1e22, mu_min=1.0, mu_max=1e6)
    config = make_config([squeezed], optimization={"multi_start": 4})

    result = fitting.fit_temperature(group, config)
    assert result.params[0] == 1e20                      # exactly the bound
    assert bool(result.at_bound_low[0]) is True
    assert bool(result.at_bound_high[0]) is False


def test_FR043_an_interior_solution_is_not_reported_as_pinned():
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]))
    config = make_config([carrier("e1", "electron")], optimization={"multi_start": 4})
    result = fitting.fit_temperature(group, config)
    assert not np.any(result.at_bound_low)
    assert not np.any(result.at_bound_high)


def test_log_encoding_round_trips_to_the_precision_the_logarithm_allows():
    """Not bit-exact, and the reason is worth knowing.

    `exp(log p)` carries a relative error of about `eps |log p|`, which for a
    density of 1e19 is 15 ulp, or 3.3e-15. That is the numerical floor of the
    whole method, and it sits nine decades below the 1e-6 of AC-008, which is
    why the round trip is achievable at all.
    """
    params = np.array([1e19, 5000.0, 3e20, 250.0])
    recovered = fitting.decode(fitting.encode(params))
    assert np.max(np.abs(recovered / params - 1.0)) < 1e-13
    with pytest.raises(ValueError):
        fitting.encode(np.array([1e19, 0.0]))


# ============================================== the window, FR-049 to FR-051

def test_FR050_and_FR051_excluded_records_are_predicted_and_scored_separately():
    """The window changes what is compared, not what is known."""
    group = make_group(TWO_BAND_TRUE, TWO_BAND_SIGN)
    inside = np.abs(group.B_T) <= 6.0
    windowed = TemperatureGroup(
        T_K=group.T_K,
        B_T=group.B_T,
        rhoxx_uohmcm=group.rhoxx_uohmcm,
        rhoxy_uohmcm=group.rhoxy_uohmcm,
        in_fit_window=inside,
        n_records_dropped=0,
        n_mirror_interpolated=0,
        n_mirror_absent=0,
    )
    config = make_config([carrier("e1", "electron"), carrier("h1", "hole")],
                         optimization={"multi_start": 6})
    result = fitting.fit_temperature(windowed, config)

    assert result.r2_outside is not None
    assert result.rmse_outside is not None
    # On noiseless data generated by this very model, the window costs nothing
    # and the excluded region is predicted as well as the fitted one.
    assert worst_relative(result.params_canonical, TWO_BAND_TRUE) < 1e-5
    assert result.rmse_outside < 1e-6 * np.max(np.abs(group.rhoxx_uohmcm))


# ==================================== per-temperature initial values and bounds

def test_FR016_an_initial_value_for_one_temperature_is_used_and_recorded():
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]), T_K=5.0)
    config = make_config(
        [carrier("e1", "electron", n_init=1e22, mu_init=5.0)],
        initial_by_temperature={"5": {"e1": {"density": 9e18, "mobility": 5200.0}}},
        optimization={"multi_start": 1},
    )
    result = fitting.fit_temperature(group, config)
    assert worst_relative(result.params, truth) < 1e-6
    assert {o["field"] for o in result.overrides} == {"init"}


def test_FR054_a_bound_for_one_temperature_is_used_and_recorded():
    truth = np.array([1.0e19, 5000.0])
    group = make_group(truth, np.array([SIGN_ELECTRON]), T_K=60.0)
    config = make_config(
        [carrier("e1", "electron", n_init=5e20)],
        overrides_by_temperature={"60": {"e1": {"density": {"min": 2e20, "max": 1e21}}}},
        optimization={"multi_start": 2},
    )
    result = fitting.fit_temperature(group, config)
    assert result.params[0] == 2e20                     # pinned to the override
    recorded = [o for o in result.overrides if o["source"] == "overrides_by_temperature"]
    assert {o["field"] for o in recorded} == {"min", "max"}
    assert recorded[0]["default"] != recorded[0]["override"]


def test_a_per_temperature_section_applies_only_to_that_temperature():
    config = make_config(
        [carrier("e1", "electron", n_init=1e19)],
        initial_by_temperature={"5": {"e1": {"density": 7e18}}},
    )
    at_five, _ = fitting.effective_carriers(config, 5.0)
    at_twenty, overrides = fitting.effective_carriers(config, 20.0)
    assert at_five[0].n_init_cm3 == 7e18
    assert at_twenty[0].n_init_cm3 == 1e19
    assert overrides == []


def test_a_temperature_key_matches_by_value_not_by_spelling():
    config = make_config(
        [carrier("e1", "electron")],
        initial_by_temperature={"5.00": {"e1": {"mobility": 4321.0}}},
    )
    specs, _ = fitting.effective_carriers(config, 5.0)
    assert specs[0].mu_init_cm2Vs == 4321.0


# ============================================================ conditioning

def test_FR055_conditioning_separates_a_determined_fit_from_a_degenerate_one():
    """Research 4.6 calibrated this. Here it is, from the machine itself."""
    determined = fitting.fit_temperature(
        make_group(TWO_BAND_TRUE, TWO_BAND_SIGN, noise=0.001, seed=5),
        make_config([carrier("e1", "electron"), carrier("h1", "hole")],
                    optimization={"multi_start": 4}),
    )

    nearly_equal = np.array([5.0e18, 6000.0, 5.0e18, 6100.0])
    degenerate = fitting.fit_temperature(
        make_group(nearly_equal, np.array([SIGN_ELECTRON, SIGN_ELECTRON]), noise=0.001, seed=5),
        make_config([carrier("e1", "electron"), carrier("e2", "electron")],
                    optimization={"multi_start": 4}),
    )

    assert determined.condition_number < 1000.0
    assert degenerate.condition_number > 1000.0
    assert determined.singular_values.size == 4
