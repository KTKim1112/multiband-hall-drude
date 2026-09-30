"""Every D_* code, from data built to trigger it. Gate 5.

Gate 5 also asks for one combination directly: the 2e+2h case of research 4.3
at 3 T must raise D_LOW_MU_B on both low-mobility carriers while raising no
D_NON_UNIQUE. That pairing is the measurement this project exists to report,
so it is asserted rather than assumed.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import diagnostics as diag
from mbfit import fitting
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE
from mbfit.dataio import Dataset, TemperatureGroup
from tests.test_roundtrip import TWO_BAND_SIGN, TWO_BAND_TRUE, carrier, make_config
from tests.test_strategies import make_dataset


def codes(found):
    return {d.code for d in found}


def by_code(found, code):
    return [d for d in found if d.code == code]


def run(dataset, config, declared=None):
    result = fitting.fit_dataset(dataset, config)
    return result, diag.collect(result, dataset, declared)


ONE = [carrier("e1", "electron", n_init=5e18, mu_init=2000.0)]
TWO = [carrier("e1", "electron", mu_init=9000.0), carrier("h1", "hole", mu_init=3000.0)]


# ============================================================ FR-048 for all

def test_FR048_every_diagnostic_states_what_it_measured_and_why():
    """The threshold and its provenance, on every entry without exception."""
    dataset = make_dataset({5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    config = make_config(
        TWO,
        optimization={
            "temperature_strategy": "global_smooth",
            "multi_start": 3,
            "loss": "soft_l1",
            "low_field_weight": {"enabled": True},
            "fit_field_range": {"enabled": True, "abs_max_T": 10.0},
        },
        smoothing={"enabled": True, "lambda_density": 1.0},
        monotonic_penalty={"enabled": True},
    )
    _, found = run(dataset, config)
    assert found
    for entry in found:
        assert entry.code
        assert entry.severity in (diag.WARNING, diag.NOTE)
        assert entry.measured is not None
        assert entry.threshold is not None
        assert entry.threshold_source, f"{entry.code} does not say where its threshold came from"
        assert set(entry.as_row()) == {
            "code", "severity", "where", "measured", "threshold", "threshold_source"
        }


# ============================================================ D_R2_BELOW

def test_D_R2_BELOW_when_the_model_cannot_reach_the_data():
    """One carrier asked to fit two, with the acceptance left at its default."""
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(ONE, optimization={"multi_start": 4}))
    assert "D_R2_BELOW" in codes(found)
    entry = by_code(found, "D_R2_BELOW")[0]
    assert entry.threshold_source in ("AC-001", "AC-002")


def test_no_D_R2_BELOW_when_the_model_is_the_one_that_made_the_data():
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(TWO, optimization={"multi_start": 4}))
    assert "D_R2_BELOW" not in codes(found)


# ============================================================ D_AT_BOUND

def test_D_AT_BOUND_when_the_truth_lies_outside_the_declared_domain():
    dataset = make_dataset({5.0: [1e19, 5000.0]}, np.array([SIGN_ELECTRON]))
    squeezed = [carrier("e1", "electron", n_init=2e20, mu_init=5000.0,
                        n_min=1e20, n_max=1e22)]
    _, found = run(dataset, make_config(squeezed, optimization={"multi_start": 3}))
    entries = by_code(found, "D_AT_BOUND")
    assert entries
    assert entries[0].where["bound"] == "min"
    assert entries[0].threshold_source == "AC-003"


def test_no_D_AT_BOUND_for_an_interior_solution():
    dataset = make_dataset({5.0: [1e19, 5000.0]}, np.array([SIGN_ELECTRON]))
    _, found = run(dataset, make_config(ONE, optimization={"multi_start": 3}))
    assert "D_AT_BOUND" not in codes(found)


# ================================================== D_JUMP and D_LABEL_SWAP

def test_D_JUMP_for_a_parameter_that_moves_by_more_than_the_allowed_factor():
    rows = {5.0: [1e19, 5000.0], 10.0: [1e21, 5000.0]}   # a hundredfold
    dataset = make_dataset(rows, np.array([SIGN_ELECTRON]))
    _, found = run(dataset, make_config(ONE, optimization={"multi_start": 3}))
    entries = by_code(found, "D_JUMP")
    assert entries
    assert entries[0].measured > entries[0].threshold
    assert entries[0].threshold_source == "AC-004"


def test_D_LABEL_SWAP_where_two_same_sign_carriers_exchange_roles():
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    rows = {
        5.0: [1e19, 9000.0, 1e20, 400.0],
        10.0: [1e20, 400.0, 1e19, 9000.0],   # the same physics, written the other way
    }
    dataset = make_dataset(rows, sign)
    config = make_config(
        [carrier("e1", "electron", n_init=1e19, mu_init=9000.0),
         carrier("e2", "electron", n_init=1e20, mu_init=400.0)],
        optimization={"multi_start": 2},
    )
    result = fitting.fit_dataset(dataset, config)
    found = diag.collect(result, dataset)
    # Whether the search lands on the relabelled solution is not something to
    # assert; what must hold is that if the order changed, it is reported.
    if result.order_changes:
        assert "D_LABEL_SWAP" in codes(found)
    swaps = by_code(found, "D_LABEL_SWAP")
    assert len(swaps) == len(result.order_changes)


def test_a_relabelling_is_not_counted_as_a_jump():
    """The comparison is made on the canonical order, so a swap costs nothing.

    Two temperatures holding the same physical solution, declared the other
    way round at the second, must produce no D_JUMP however large the
    apparent index-by-index change.
    """
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    first = np.array([1e19, 9000.0, 1e20, 400.0])
    swapped = np.array([1e20, 400.0, 1e19, 9000.0])

    class Fit:
        def __init__(self, T_K, params):
            from mbfit.core.canonical import canonicalise
            self.T_K = T_K
            self.params = params
            self.params_canonical = canonicalise(params, sign)
            self.specs = tuple(
                cfg.CarrierSpec(f"e{i+1}", "electron", 1e19, 1e14, 1e24, 1e3, 1.0, 1e6)
                for i in range(2)
            )

    result = fitting.RunResult(
        config=make_config([carrier("e1", "electron"), carrier("e2", "electron")]),
        fits=(Fit(5.0, first), Fit(10.0, swapped)),
        strategy="independent",
        seed=1,
        order_changes=(0,),
    )
    found = diag.jumps_and_swaps(result)
    assert "D_LABEL_SWAP" in codes(found)
    assert "D_JUMP" not in codes(found)


# ============================================================ D_NON_UNIQUE

def test_D_NON_UNIQUE_when_equivalent_starts_reach_different_answers():
    """Two electrons of exactly equal mobility: only their sum is determined.

    The flattest valley there is. Different starts split the total between
    the two carriers differently at identical cost, which is precisely the
    situation FR-045 exists to report.
    """
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    dataset = make_dataset({5.0: [5e18, 6000.0, 5e18, 6000.0]}, sign)
    config = make_config(
        [carrier("e1", "electron", n_init=5e18, mu_init=6000.0),
         carrier("e2", "electron", n_init=5e18, mu_init=6000.0)],
        optimization={"multi_start": 5, "multi_start_log_sigma": 0.4},
    )
    _, found = run(dataset, config)
    entries = by_code(found, "D_NON_UNIQUE")
    assert entries
    assert entries[0].threshold_source == "AC-006"


def test_no_D_NON_UNIQUE_when_the_starts_all_agree():
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(TWO, optimization={"multi_start": 6}))
    assert "D_NON_UNIQUE" not in codes(found)


# ==================================================== D_RESIDUAL_STRUCTURE

def test_D_RESIDUAL_STRUCTURE_for_a_systematic_departure():
    """One carrier fitted to two: the residual keeps its sign for stretches."""
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(ONE, optimization={"multi_start": 4}))
    entries = by_code(found, "D_RESIDUAL_STRUCTURE")
    assert entries
    assert entries[0].threshold_source == "AC-007"


# ============================================================== D_LOW_MU_B

def test_D_LOW_MU_B_names_the_carrier_the_field_range_cannot_resolve():
    """Research 4.3, at the field range that produced the 35 % error."""
    truth = np.array([1.46e19, 6038.0, 8.91e20, 497.0, 8.86e18, 6101.0, 1.01e21, 265.0])
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON, SIGN_HOLE, SIGN_HOLE])
    dataset = make_dataset({5.0: truth}, sign, fields=np.linspace(-3.0, 3.0, 49))
    config = make_config(
        [carrier("e1", "electron", n_init=1.5e19, mu_init=6000.0),
         carrier("e2", "electron", n_init=9e20, mu_init=500.0),
         carrier("h1", "hole", n_init=9e18, mu_init=6100.0),
         carrier("h2", "hole", n_init=1e21, mu_init=265.0)],
        optimization={"multi_start": 3},
    )
    _, found = run(dataset, config)
    slow = by_code(found, "D_LOW_MU_B")
    assert {entry.where["carrier"] for entry in slow} >= {"e2", "h2"}
    for entry in slow:
        assert entry.measured < 1.0
        assert entry.threshold == 1.0


def test_GATE5_the_pairing_this_project_exists_to_report():
    """D_LOW_MU_B on both slow carriers, and no D_NON_UNIQUE, at 3 T.

    R-squared clears its acceptance while a density is badly determined. That
    combination is the whole argument of research 4.3, and Gate 5 asks for it
    directly.
    """
    truth = np.array([1.46e19, 6038.0, 8.91e20, 497.0, 8.86e18, 6101.0, 1.01e21, 265.0])
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON, SIGN_HOLE, SIGN_HOLE])
    dataset = make_dataset({5.0: truth}, sign, fields=np.linspace(-3.0, 3.0, 49))
    config = make_config(
        [carrier("e1", "electron", n_init=1.46e19, mu_init=6038.0),
         carrier("e2", "electron", n_init=8.91e20, mu_init=497.0),
         carrier("h1", "hole", n_init=8.86e18, mu_init=6101.0),
         carrier("h2", "hole", n_init=1.01e21, mu_init=265.0)],
        optimization={"multi_start": 4},
    )
    result, found = run(dataset, config)

    slow = {entry.where["carrier"] for entry in by_code(found, "D_LOW_MU_B")}
    assert {"e2", "h2"} <= slow
    assert "D_NON_UNIQUE" not in codes(found)
    assert result.fits[0].r2_rhoxx > 0.995
    assert result.fits[0].r2_rhoxy > 0.995


# ================================= D_FIELD_RANGE_ACTIVE, D_EXCLUDED_MISMATCH

def test_D_FIELD_RANGE_ACTIVE_and_the_count_it_removed():
    config = make_config(
        TWO,
        optimization={"multi_start": 3,
                      "fit_field_range": {"enabled": True, "abs_max_T": 6.0}},
    )
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN, config=config)
    _, found = run(dataset, config)
    entries = by_code(found, "D_FIELD_RANGE_ACTIVE")
    assert entries and entries[0].measured > 0


def test_D_EXCLUDED_MISMATCH_when_the_excluded_region_disagrees():
    """Data that changes character outside the window the fit was given.

    Built rather than hoped for: the longitudinal channel is multiplied by
    1.5 beyond 6 T, so the region the fit never saw genuinely disagrees with
    the region it did. That is what the diagnostic is for, and what the
    reference sample turned out to do for real.
    """
    from mbfit.dataio import field_window_mask

    config = make_config(
        TWO,
        optimization={"multi_start": 4,
                      "fit_field_range": {"enabled": True, "abs_max_T": 6.0}},
    )
    fields = np.linspace(-14.0, 14.0, 57)
    rho_xx, rho_xy = fitting.model_resistivity(fields, TWO_BAND_TRUE, TWO_BAND_SIGN)
    rho_xx = np.where(np.abs(fields) > 6.0, rho_xx * 1.5, rho_xx)
    dataset = Dataset(
        groups=(
            TemperatureGroup(
                T_K=5.0,
                B_T=fields,
                rhoxx_uohmcm=rho_xx,
                rhoxy_uohmcm=rho_xy,
                in_fit_window=field_window_mask(fields, config),
                n_records_dropped=0,
                n_mirror_interpolated=0,
                n_mirror_absent=0,
            ),
        ),
        n_records_dropped=0,
    )
    _, found = run(dataset, config)
    entries = by_code(found, "D_EXCLUDED_MISMATCH")
    assert entries
    assert entries[0].measured > entries[0].threshold
    assert entries[0].threshold_source == "AC-009"


def test_no_field_range_diagnostics_when_the_window_is_off():
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(TWO, optimization={"multi_start": 3}))
    assert "D_FIELD_RANGE_ACTIVE" not in codes(found)
    assert "D_EXCLUDED_MISMATCH" not in codes(found)


# ======================================================== D_ILL_CONDITIONED

def test_D_ILL_CONDITIONED_for_two_carriers_that_cannot_be_told_apart():
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    dataset = make_dataset({5.0: [5e18, 6000.0, 5e18, 6100.0]}, sign)
    config = make_config(
        [carrier("e1", "electron", n_init=5e18, mu_init=6000.0),
         carrier("e2", "electron", n_init=5e18, mu_init=6100.0)],
        optimization={"multi_start": 2},
    )
    _, found = run(dataset, config)
    entries = by_code(found, "D_ILL_CONDITIONED")
    assert entries
    assert entries[0].measured > 1000.0
    assert entries[0].threshold_source == "AC-010"


def test_no_D_ILL_CONDITIONED_for_the_well_determined_case():
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(TWO, optimization={"multi_start": 3}))
    assert "D_ILL_CONDITIONED" not in codes(found)


# ========================================================= D_BOUND_OVERRIDE

def test_D_BOUND_OVERRIDE_reports_the_default_beside_the_override():
    dataset = make_dataset({60.0: [1e19, 5000.0]}, np.array([SIGN_ELECTRON]))
    config = make_config(
        [carrier("e1", "electron", n_init=5e20)],
        overrides_by_temperature={"60": {"e1": {"density": {"min": 2e20, "max": 1e21}}}},
        optimization={"multi_start": 2},
    )
    _, found = run(dataset, config)
    entries = by_code(found, "D_BOUND_OVERRIDE")
    assert entries
    assert {entry.where["field"] for entry in entries} == {"min", "max"}
    assert entries[0].measured != entries[0].threshold


# ============================== D_PRIORS_ACTIVE and D_PRIORS_DISABLED, FR-056

def test_D_PRIORS_ACTIVE_names_every_soft_prior_in_force():
    dataset = make_dataset({5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    declared = make_config(
        [dict(carrier("e1", "electron", mu_init=9000.0), monotonic_density="decrease"),
         carrier("h1", "hole", mu_init=3000.0)],
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2,
                      "loss": "soft_l1",
                      "low_field_weight": {"enabled": True}},
        smoothing={"enabled": True, "lambda_density": 1.0},
        monotonic_penalty={"enabled": True},
    )
    _, found = run(dataset, declared)
    active = by_code(found, "D_PRIORS_ACTIVE")
    named = {entry.where["prior"] for entry in active}
    assert named == {"temperature_coupling", "monotonic", "low_field_emphasis", "robust_loss"}
    assert {entry.threshold_source for entry in active} == {
        "ledger C3", "ledger C4", "ledger C5", "ledger C6"
    }


def test_nothing_announces_itself_when_no_prior_is_in_force():
    dataset = make_dataset({5.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    _, found = run(dataset, make_config(TWO, optimization={"multi_start": 2}))
    assert "D_PRIORS_ACTIVE" not in codes(found)


def test_D_PRIORS_DISABLED_records_what_the_switch_silenced():
    dataset = make_dataset({5.0: TWO_BAND_TRUE, 10.0: TWO_BAND_TRUE}, TWO_BAND_SIGN)
    declared = make_config(
        TWO,
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2,
                      "loss": "soft_l1"},
        smoothing={"enabled": True, "lambda_density": 1.0},
    )
    stripped = cfg.disable_soft_priors(declared)
    _, found = run(dataset, stripped, declared=declared)
    entries = by_code(found, "D_PRIORS_DISABLED")
    assert entries
    assert entries[0].measured["smoothing"] is True
    assert entries[0].measured["loss"] == "soft_l1"
    assert "D_PRIORS_ACTIVE" not in codes(found)


# ================================================ D_RECORDS_DROPPED, D_MIRROR_ABSENT

def test_D_RECORDS_DROPPED_and_D_MIRROR_ABSENT(tmp_path):
    from mbfit import dataio
    from tests.test_dataio import COLUMNS, write_csv

    fields = np.linspace(0.0, 9.0, 10)          # one-sided: every mirror absent
    rows = [(5.0, b, 10.0 + 0.3 * b, 0.5 * b) for b in fields]
    rows.append((5.0, "bad", 1.0, 1.0))         # one unusable record
    path = write_csv(tmp_path, rows)

    config = cfg.resolve({
        "schema_version": "1.0",
        "columns": COLUMNS,
        "carriers": ONE,
        "preprocess": {"symmetrize_rhoxx": True},
        "optimization": {"multi_start": 2},
    })
    dataset = dataio.load_dataset(path, config)
    result = fitting.fit_dataset(dataset, config)
    found = diag.collect(result, dataset)

    assert "D_RECORDS_DROPPED" in codes(found)
    assert "D_MIRROR_ABSENT" in codes(found)
    assert by_code(found, "D_RECORDS_DROPPED")[0].measured == 1


# ===================================================================== order

def test_conditioning_is_reported_first():
    """The one line that says whether the data determined the answer at all."""
    sign = np.array([SIGN_ELECTRON, SIGN_ELECTRON])
    dataset = make_dataset({5.0: [5e18, 6000.0, 5e18, 6100.0]}, sign)
    config = make_config(
        [carrier("e1", "electron", n_init=5e18, mu_init=6000.0),
         carrier("e2", "electron", n_init=5e18, mu_init=6100.0)],
        optimization={"multi_start": 2},
    )
    _, found = run(dataset, config)
    assert found[0].code == "D_ILL_CONDITIONED"
