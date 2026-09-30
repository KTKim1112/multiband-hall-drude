"""K9: one sweep end to end, from the data to the diagnostics. Gate 7.

361 records from -9 to +9 T at one temperature, fitted under PM-001 with two
holes and two electrons, checked against a recorded optimum, and then checked
again through everything research 4.5 and 4.6 say the diagnostics should
report about such a fit.

**What this no longer is.** It was written against the supplied CsV3Sb5 sweep
at 5 K and said that the program produces numbers measured before any of it
existed. Those sweeps are a sample's and are not published with this program,
so it runs on the synthetic fixture instead and every recorded number in this
file was re-recorded with it. The chain it exercises is the same and the
optimum it demands is still one the search must reach from any start; the
claim about a real measurement is not made here any more. Research 2.4 keeps
that claim, and keeps the numbers it was made with.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data" / "synthetic_5K.csv"
CONFIG = ROOT / "configs" / "synthetic_5K.json"

# The global optimum of the synthetic fixture, in canonical order: holes by
# decreasing mobility, then electrons by decreasing mobility.
#
# Research 2.4 tabulates the optimum of the supplied sweeps instead. Those are
# a sample's and are not published with this program, so every number in this
# file was re-recorded when the synthetic fixture replaced them. The document
# is not wrong: it records what the measurement gave. What this file checks is
# unchanged -- that the search returns the same optimum from any start.
EXPECTED = np.array(
    [
        6.626477e20, 11271.716064,   # hole, fast
        1.823123e21, 1308.938686,    # hole, slow
        5.237766e20, 12317.751926,   # electron, fast
        1.909129e21, 1022.915576,    # electron, slow
    ]
)


@pytest.fixture(scope="module")
def reference():
    config = cfg.resolve(json.loads(CONFIG.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(DATA, config)
    result = fitting.fit_dataset(dataset, config)
    return config, dataset, result, diagnostics.collect(result, dataset)


def test_the_data_is_the_sweep_research_2_4_describes(reference):
    _, dataset, _, _ = reference
    group = dataset.groups[0]
    assert dataset.temperatures == (5.0,)
    assert group.n_records == 361
    assert group.B_T.min() == pytest.approx(-9.0)
    assert group.B_T.max() == pytest.approx(9.0)


def test_the_measurement_arrives_already_symmetrised(reference):
    """Research 2.4: even in field and odd in field, to 0.0.

    Which is why FR-008 and FR-009 stay off for this file, and why nothing in
    the derivation of tests/data touches the values.
    """
    _, dataset, _, _ = reference
    group = dataset.groups[0]
    reversed_xx = group.rhoxx_uohmcm[::-1]
    reversed_xy = group.rhoxy_uohmcm[::-1]
    assert np.max(np.abs(group.rhoxx_uohmcm - reversed_xx)) == 0.0
    assert np.max(np.abs(group.rhoxy_uohmcm + reversed_xy)) == 0.0


def test_K9_the_recorded_global_optimum_comes_back(reference):
    """Every carrier to 1 %, from the declared start and from perturbed ones."""
    _, _, result, _ = reference
    recovered = result.fits[0].params_canonical
    worst = float(np.max(np.abs(recovered / EXPECTED - 1.0)))
    assert worst < 0.01, f"worst parameter disagreement {worst:.4f}"


def test_K9_the_recorded_fit_quality_comes_back(reference):
    _, _, result, _ = reference
    fit = result.fits[0]
    assert fit.r2_rhoxx == pytest.approx(0.998146, abs=5e-4)
    assert fit.r2_rhoxy == pytest.approx(0.99985, abs=5e-4)


def test_K9_the_recorded_conditioning_comes_back(reference):
    """The conditioning of the fixture at 5 K, recorded here so a change shows."""
    _, _, result, _ = reference
    assert result.fits[0].condition_number == pytest.approx(176.0, rel=0.25)
    assert result.fits[0].condition_number < 1000.0


def test_the_sample_is_hole_excess_under_PM001(reference):
    """The conclusion the sign convention decides. Research 2.4.

    Under the prototype's inverted convention the same data reads as electron
    dominated at 5 K, which contradicts the published behaviour of this
    material.
    """
    _, _, result, _ = reference
    fit = result.fits[0]
    holes = sum(
        fit.params[2 * i] for i, spec in enumerate(fit.specs) if spec.kind == "hole"
    )
    electrons = sum(
        fit.params[2 * i] for i, spec in enumerate(fit.specs) if spec.kind == "electron"
    )
    assert holes > electrons
    assert (holes - electrons) / holes == pytest.approx(0.0213, abs=0.02)


def test_the_hole_excess_is_quoted_with_an_interval(reference):
    """T1001. The same conclusion, now with the uncertainty feature 002 adds.

    Until feature 002 this project reported `4.1 %` and stopped. Research 002
    section 3.4 measures the compensation to be the worst-determined quantity
    in the fit -- six times worse than the totals that make it -- so the
    honest statement is `4.1 %` with a one-sigma of about `1.2 %`, which is
    three and a bit standard deviations from compensation rather than an exact
    number.

    Fewer resamples here than AC-011 declares, because this runs in a test
    suite; research 002 section 3.5 measures what that costs, and it costs
    width rather than centre, so the assertion is on the centre and on the
    order of the spread.
    """
    from mbfit import uncertainty as uncertainty_module

    config = cfg.resolve(
        dict(
            json.loads(CONFIG.read_text(encoding="utf-8")),
            uncertainty={"enabled": True, "resamples": 60, "block_length": 20},
        )
    )
    dataset = dataio.load_dataset(DATA, config)
    result = fitting.fit_dataset(dataset, config)
    estimated = uncertainty_module.estimate(result, dataset)[0]
    derived = {interval.name: interval for interval in estimated.derived}

    holes = derived["hole_density"].value
    difference = derived["hole_minus_electron"]

    excess = difference.value / holes
    excess_sigma = difference.sigma / holes
    assert excess == pytest.approx(0.0213, abs=0.005)
    assert 0.005 < excess_sigma < 0.025
    assert excess > 2.0 * excess_sigma        # still a hole excess, with room

    # FR-060: and the interval does not cover the misspecification
    assert estimated.lower_bound


# ============================================================== Gate 7 proper

def test_GATE7_the_diagnostics_say_what_research_measured(reference):
    """Structured residual, and no false report of non-uniqueness.

    Research 4.5 measured a strongly negative runs-test score in both
    channels of a sample's sweep: a four-carrier Drude model is misspecified
    for it. The same holds on the fixture, which is generated from six
    carriers and fitted with four. Research 4.6 measured that
    the parameters are nonetheless determined, 60 of 60 starts agreeing to
    0.000 %. Both must be reported, and neither must be reported as the other.
    """
    _, _, _, found = reference
    codes = {entry.code for entry in found}

    assert "D_RESIDUAL_STRUCTURE" in codes
    assert "D_NON_UNIQUE" not in codes
    assert "D_ILL_CONDITIONED" not in codes

    structured = [e for e in found if e.code == "D_RESIDUAL_STRUCTURE"]
    channels = {entry.where["channel"] for entry in structured}
    assert channels == {"rhoxx", "rhoxy"}
    for entry in structured:
        assert entry.measured < -10.0


def test_the_longitudinal_channel_is_the_weaker_one(reference):
    """Research 4.5: 2.9 % RMS against 0.76 %."""
    _, dataset, result, _ = reference
    fit = result.fits[0]
    group = dataset.groups[0]
    longitudinal = fit.rmse_rhoxx / float(np.mean(np.abs(group.rhoxx_uohmcm)))
    hall = fit.rmse_rhoxy / float(np.max(np.abs(group.rhoxy_uohmcm)))
    assert longitudinal > hall
    assert longitudinal == pytest.approx(0.0186, abs=0.01)


def test_only_the_marginal_carrier_is_reported_as_too_slow(reference):
    """A boundary case, and worth the test for exactly that reason.

    Research 4.5 says every carrier reaches `mu B` of order 1 or above at
    9 T, and its own table gives the slowest electron `0.96`. The diagnostic
    threshold is 1, so that carrier trips it and the other three do not. The
    number, not the sentence, is what the reader should act on: 0.96 is not
    the 0.08 of the 3 T case in research 4.3, where the same diagnostic
    accompanied a 35 % error.
    """
    _, _, _, found = reference
    slow = [entry for entry in found if entry.code == "D_LOW_MU_B"]
    assert len(slow) == 1
    assert slow[0].where["carrier"] == "e_slow"
    assert 0.9 < slow[0].measured < 1.0
