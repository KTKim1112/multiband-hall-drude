"""Phase 9 — the resampling interval. Gate 9.

The decisive test here is the coverage one, AC-016. An interval is a promise
about how often it contains the truth, and the only way to check that promise
is to know the truth and count. Everything else in this file is plumbing
around that.

The coverage case uses independent noise and a block length of 1, which is the
matching pair: block resampling exists to carry correlation that this data
does not have, and using a long block on independent residuals would widen the
interval past its nominal rate. Research 002 section 3.2 records the opposite
case, where the residual is correlated and a block length of 1 is the wrong
choice.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting, uncertainty
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "configs" / "synthetic_5K.json"

FIELDS = np.round(np.linspace(-9.0, 9.0, 81), 6)
TRUE_DENSITY = [8.0e20, 5.0e20]
TRUE_MOBILITY = [9000.0, 14000.0]
TRUE_SIGN = [SIGN_HOLE, SIGN_ELECTRON]
NOISE_FRACTION = 0.002

TRIALS = 100
RESAMPLES = 100


def _clean():
    xx, xy = resistivity(
        FIELDS, density_to_si(TRUE_DENSITY), mobility_to_si(TRUE_MOBILITY), TRUE_SIGN
    )
    return resistivity_from_si(xx), resistivity_from_si(xy)


def _two_carrier_config(**uncertainty_settings):
    document = {
        "schema_version": "1.0",
        "columns": {"T": "T(K)", "B": "B(T)", "rhoxx": "a", "rhoxy": "b"},
        "carriers": [
            {"name": "h", "kind": "hole",
             "density": {"init": TRUE_DENSITY[0], "min": 1e17, "max": 1e23},
             "mobility": {"init": TRUE_MOBILITY[0], "min": 1.0, "max": 1e6}},
            {"name": "e", "kind": "electron",
             "density": {"init": TRUE_DENSITY[1], "min": 1e17, "max": 1e23},
             "mobility": {"init": TRUE_MOBILITY[1], "min": 1.0, "max": 1e6}},
        ],
        "optimization": {"multi_start": 1},
        "uncertainty": dict(
            {"enabled": True, "resamples": RESAMPLES, "block_length": 1},
            **uncertainty_settings,
        ),
    }
    return cfg.resolve(document)


def _group(rhoxx, rhoxy):
    return dataio.TemperatureGroup(
        T_K=5.0,
        B_T=FIELDS,
        rhoxx_uohmcm=rhoxx,
        rhoxy_uohmcm=rhoxy,
        in_fit_window=np.ones(FIELDS.size, dtype=bool),
        n_records_dropped=0,
        n_mirror_interpolated=0,
        n_mirror_absent=0,
    )


# ============================================================ Gate 9, AC-016

@pytest.mark.slow
def test_GATE9_the_interval_covers_the_truth_at_about_the_declared_rate():
    """AC-016. An interval that does not cover is not an interval.

    100 synthetic data sets from known carriers plus independent noise. For
    each, the central 68 % of the resampled distribution is taken, and the
    generating value either falls inside it or does not.

    Research 002 section 3.5 measures the achieved rate at 0.635 with a
    binomial standard deviation of 0.033, a little below nominal: the interval
    is slightly narrow rather than slightly wide, which is the direction that
    matters and the reason the shortfall is recorded rather than rounded away.

    **The resampling seed is varied per trial, and it has to be.** The program
    derives that seed from the configuration so that FR-037 holds and a run
    reproduces, which means every trial here would otherwise draw the same
    block pattern and the trials would not be independent. Measured on two
    fixed-seed runs of this same setup: 0.585 and 0.715. Neither is the
    coverage; both are one pattern's luck.
    """
    clean_xx, clean_xy = _clean()
    truth = np.array(
        [TRUE_DENSITY[0], TRUE_MOBILITY[0], TRUE_DENSITY[1], TRUE_MOBILITY[1]]
    )
    scale_xx = NOISE_FRACTION * float(np.abs(clean_xx).mean())
    scale_xy = NOISE_FRACTION * float(np.max(np.abs(clean_xy)))

    generator = np.random.default_rng(20260912)
    inside = np.zeros(truth.size, dtype=int)
    for trial in range(TRIALS):
        config = _two_carrier_config(seed=1000 + trial)
        group = _group(
            clean_xx + generator.normal(scale=scale_xx, size=FIELDS.size),
            clean_xy + generator.normal(scale=scale_xy, size=FIELDS.size),
        )
        fit = fitting.fit_temperature(group, config)
        estimated = uncertainty.resample_temperature(fit, group, config)
        for column, interval in enumerate(estimated.parameters):
            if interval.low <= truth[column] <= interval.high:
                inside[column] += 1

    coverage = inside / TRIALS
    assert np.all(coverage >= 0.50), f"under-covering: {coverage}"
    assert np.all(coverage <= 0.85), f"over-covering: {coverage}"
    assert 0.55 <= coverage.mean() <= 0.78, f"mean coverage {coverage.mean():.3f}"


def test_a_deliberately_narrow_interval_fails_the_coverage_check():
    """The check has to be able to fail, or it is not checking anything.

    Same data, same fits, but the interval is taken at a tenth of its width.
    If coverage stayed near 0.68 under that, the test above would be passing
    on something other than the interval.
    """
    clean_xx, clean_xy = _clean()
    config = _two_carrier_config()
    truth = np.array(
        [TRUE_DENSITY[0], TRUE_MOBILITY[0], TRUE_DENSITY[1], TRUE_MOBILITY[1]]
    )
    scale_xx = NOISE_FRACTION * float(np.abs(clean_xx).mean())
    scale_xy = NOISE_FRACTION * float(np.max(np.abs(clean_xy)))

    generator = np.random.default_rng(31337)
    inside = 0
    trials = 25
    for _ in range(trials):
        group = _group(
            clean_xx + generator.normal(scale=scale_xx, size=FIELDS.size),
            clean_xy + generator.normal(scale=scale_xy, size=FIELDS.size),
        )
        fit = fitting.fit_temperature(group, config)
        estimated = uncertainty.resample_temperature(fit, group, config)
        interval = estimated.parameters[0]
        centre = 0.5 * (interval.low + interval.high)
        half = 0.05 * (interval.high - interval.low)
        if centre - half <= truth[0] <= centre + half:
            inside += 1
    assert inside / trials < 0.45


# ------------------------------------------------------- shape and bookkeeping

@pytest.fixture(scope="module")
def reference():
    document = json.loads(REFERENCE.read_text(encoding="utf-8"))
    document["uncertainty"] = {"enabled": True, "resamples": 40, "block_length": 20}
    config = cfg.resolve(document)
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    return config, dataset, result, uncertainty.estimate(result, dataset)


def test_the_feature_is_off_unless_asked_for():
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    assert uncertainty.estimate(result, dataset) == ()


def test_every_parameter_and_derived_quantity_gets_an_interval(reference):
    _, _, result, estimated = reference
    entry = estimated[0]
    assert len(entry.parameters) == result.fits[0].params.size
    assert tuple(interval.name for interval in entry.derived) == uncertainty.DERIVED
    for interval in entry.parameters + entry.derived:
        assert interval.low <= interval.value <= interval.high or interval.sigma > 0.0
        assert interval.sigma >= 0.0


def test_the_block_length_and_count_are_recorded(reference):
    """FR-059: the declaration has to travel with the number it produced."""
    _, _, _, estimated = reference
    entry = estimated[0]
    assert entry.block_length == 20
    assert entry.resamples == 40
    assert entry.samples.shape == (40, 8)


def test_the_totals_are_better_determined_than_the_carriers(reference):
    """Research 002 section 3.4, the result this feature exists for.

    The individual fast densities move by several percent and their sum by
    about two, because the data constrains the total far better than the
    split. Reporting eight parameters with eight intervals would hide that.
    """
    _, _, _, estimated = reference
    by_name = {interval.name: interval for interval in estimated[0].parameters}
    derived = {interval.name: interval for interval in estimated[0].derived}

    fast_hole = by_name["canonical1_hole_density"]
    fast_hole_relative = fast_hole.sigma / fast_hole.value
    holes = derived["hole_density"]
    holes_relative = holes.sigma / holes.value

    assert fast_hole_relative > 3.0 * holes_relative
    assert holes_relative < 0.05


def test_the_compensation_is_the_worst_determined_quantity(reference):
    """4.1 % hole excess, but with an interval on it. Research 002 section 3.4."""
    _, _, _, estimated = reference
    derived = {interval.name: interval for interval in estimated[0].derived}
    difference = derived["hole_minus_electron"]
    holes = derived["hole_density"]

    relative = difference.sigma / abs(difference.value)
    assert relative > 5.0 * (holes.sigma / holes.value)
    assert 0.15 < relative < 0.45
    # and the excess is still away from zero at more than two of these
    assert abs(difference.value) > 2.0 * difference.sigma


def test_the_correlation_matrix_pairs_the_two_fast_densities(reference):
    """Research 002 section 3.3 measured +0.9 at every block length tried."""
    _, _, _, estimated = reference
    entry = estimated[0]
    index = {name: column for column, name in enumerate(entry.names)}
    value = entry.correlation[
        index["canonical1_hole_density"], index["canonical3_electron_density"]
    ]
    assert value > 0.7


def test_a_structured_residual_marks_the_interval_as_a_lower_bound(reference):
    """FR-060, and the reference sweep is exactly that case."""
    _, dataset, result, estimated = reference
    assert estimated[0].lower_bound
    found = diagnostics.collect(result, dataset, None, estimated)
    assert any(entry.code == "D_INTERVAL_LOWER_BOUND" for entry in found)


def test_independent_noise_does_not_mark_a_lower_bound():
    """The flag has to distinguish, or it is decoration."""
    clean_xx, clean_xy = _clean()
    config = _two_carrier_config()
    generator = np.random.default_rng(5)
    group = _group(
        clean_xx + generator.normal(scale=NOISE_FRACTION * np.abs(clean_xx).mean(), size=FIELDS.size),
        clean_xy + generator.normal(scale=NOISE_FRACTION * np.max(np.abs(clean_xy)), size=FIELDS.size),
    )
    dataset = dataio.Dataset(groups=(group,), n_records_dropped=0)
    result = fitting.fit_dataset(dataset, config)
    estimated = uncertainty.estimate(result, dataset)
    assert not estimated[0].lower_bound


def test_the_run_reproduces(reference):
    """FR-037 reaches the intervals too: same configuration, same numbers."""
    config, dataset, result, estimated = reference
    again = uncertainty.estimate(result, dataset)
    assert np.array_equal(again[0].samples, estimated[0].samples)
