"""T1204 -- the eight spectrum diagnostics, each raised from data. Gate 12.

They divide into two groups: what the extension of step 2 did, and what the
inversion of step 5 could settle. The second group is per carrier type,
because after separation the hole and electron problems succeed and fail
independently, and a clean hole branch beside an unresolved electron one is a
real state that has to be reportable.

A code no data raises is a code nobody has checked. Six of the eight are
provoked by running the whole pipeline on a sweep built to carry the
condition. The remaining two -- `D_SPECTRUM_NEGATIVE_PART` and
`D_SPECTRUM_AMBIGUOUS` -- are the two that NR-011 and the separation were
introduced to make unreachable, so no sweep produces them any more and they
are provoked from the records that carry the condition instead. That is the
honest test: the mapping from a state to a code is what is under test, and
manufacturing a sweep that reached those states would mean weakening the
constraint that prevents them.

The synthetic carrier set below is arbitrary, chosen for this project.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting, spectrum
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

FIELDS = np.round(np.linspace(-9.0, 9.0, 121), 6)

SIX_DENSITY = [3.0e19, 6.0e20, 1.4e21, 8.0e19, 4.0e20, 1.6e21]
SIX_MOBILITY = [45000.0, 12000.0, 1500.0, 33000.0, 9000.0, 800.0]
SIX_SIGN = [SIGN_HOLE] * 3 + [SIGN_ELECTRON] * 3


def _run(noise=0.0, **spectrum_settings):
    """The whole pipeline on the six-carrier set, and the codes it raised."""
    xx, xy = resistivity(
        FIELDS, density_to_si(SIX_DENSITY), mobility_to_si(SIX_MOBILITY), SIX_SIGN
    )
    xx, xy = resistivity_from_si(xx), resistivity_from_si(xy)
    if noise:
        generator = np.random.default_rng(0)
        xx = xx + generator.normal(scale=noise * np.abs(xx).mean(), size=FIELDS.size)
        xy = xy + generator.normal(scale=noise * np.max(np.abs(xy)), size=FIELDS.size)
    group = dataio.TemperatureGroup(
        T_K=5.0, B_T=FIELDS, rhoxx_uohmcm=xx, rhoxy_uohmcm=xy,
        in_fit_window=np.ones(FIELDS.size, dtype=bool),
        n_records_dropped=0, n_mirror_interpolated=0, n_mirror_absent=0,
    )
    config = cfg.resolve({
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
        "optimization": {"multi_start": 2},
        "spectrum": dict(
            {"enabled": True, "lorentzian_terms": 6, "lorentzian_multi_start": 12},
            **spectrum_settings,
        ),
    })
    dataset = dataio.Dataset(groups=(group,), n_records_dropped=0)
    result = fitting.fit_dataset(dataset, config)
    spectra = spectrum.estimate(result, dataset)
    found = diagnostics.collect(result, dataset, None, (), spectra)
    return {entry.code for entry in found if entry.code.startswith("D_SPECTRUM")}, spectra[0]


# ------------------------------------------------------- what the extension did

@pytest.mark.slow
def test_the_reference_sweep_raises_only_the_note():
    """The one state the six-carrier set is actually in, measured not assumed.

    At six terms on six carriers the extension reproduces the data to
    `2.7e-5` relative, every branch reaches its noise target, both counts sit
    on one plateau, and the proposal is the carrier set that generated it. The
    only code raised is the multimodal note of the test below. Pinning the
    whole set rather than a chosen subset is what makes the tests that follow
    mean something: each one adds exactly one code to this.
    """
    codes, entry = _run()
    assert codes == {"D_SPECTRUM_EXTENSION_MULTIMODAL"}
    assert entry.proposal == {"hole": 3, "electron": 3}
    assert entry.extension.max_relative_residual < 1e-4
    assert all(branch.noise_reached for branch in entry.branches)
    assert all(len(branch.plateaus) == 1 for branch in entry.branches)


@pytest.mark.slow
def test_too_few_terms_raises_the_underfit_code():
    """AC-021. An order below the number of distinct mobilities cannot fit.

    This is the signal that makes the order a declared knob rather than a
    trap: the failure shows up in the residual, which a reader can see without
    knowing the answer. Measured, three terms on six carriers leave `3.7e-2`
    where six terms leave `2.7e-5` -- three orders of magnitude, against a
    threshold of ten times the noise.
    """
    codes, entry = _run(lorentzian_terms=3)
    assert "D_SPECTRUM_EXTENSION_UNDERFIT" in codes
    assert entry.extension.max_relative_residual > 10.0 * max(entry.noise)

    codes, _ = _run(lorentzian_terms=6)
    assert "D_SPECTRUM_EXTENSION_UNDERFIT" not in codes


@pytest.mark.slow
def test_a_mobility_range_that_excludes_carriers_raises_the_saturated_code():
    """FR-069. When a term sits on the declared bound, the bound chose it.

    The true mobilities span `800` to `45000`; the range below admits `2000`
    to `20000`. Terms pile up on both ends, the proposal collapses to one
    carrier per sign, and the code says the range and not the data decided it.
    """
    codes, entry = _run(mu_min_cm2Vs=2000.0, mu_max_cm2Vs=20000.0)
    assert "D_SPECTRUM_EXTENSION_SATURATED" in codes
    assert entry.extension.at_bound
    assert entry.proposal == {"hole": 1, "electron": 1}


@pytest.mark.slow
def test_the_multimodal_note_is_raised_and_is_not_cured_by_more_starts():
    """FR-068. Fewer than half the starts agreeing means a choice was made.

    A longer search does not settle it: exactly **one** start reaches the best
    cost at 12, at 24 and at 48 starts. The reason is specific to noiseless
    data and worth knowing, because it is the reverse of the usual worry.
    Agreement counts the starts within `1 %` of the best cost, and on data
    with no noise the best cost is near zero, so `1 %` of it is a band nothing
    else can fit inside. The note fires because the fit is *too* good, not
    because it is unstable -- the proposal is `3 + 3` at every start count
    tried. Research 003 section 3.2.1 measures the same statistic swinging
    between `1` and `19` of 30 on noisy data, which is why FR-068 makes it a
    note to read beside the answer rather than a verdict on it.
    """
    codes, entry = _run()
    assert "D_SPECTRUM_EXTENSION_MULTIMODAL" in codes
    assert entry.extension.n_starts_agreeing * 2 < entry.extension.n_starts

    wider, entry = _run(lorentzian_multi_start=24)
    assert "D_SPECTRUM_EXTENSION_MULTIMODAL" in wider
    assert entry.proposal == {"hole": 3, "electron": 3}

    # and it is genuinely about agreement, not about the fit being bad: the
    # narrowed range above fits a smaller problem, 9 of 12 starts agree, and
    # the note is silent even though the answer there is worse.
    narrow, entry = _run(mu_min_cm2Vs=2000.0, mu_max_cm2Vs=20000.0)
    assert "D_SPECTRUM_EXTENSION_MULTIMODAL" not in narrow
    assert entry.extension.n_starts_agreeing * 2 >= entry.extension.n_starts


@pytest.mark.slow
def test_switching_off_the_constraint_is_reported():
    """NR-011 is a prior, so turning it off is recorded. Article X.

    Unconstrained, the same sweep fits to `2.9e-14` -- a thousand times better
    than the constrained form reaches. That is the whole difficulty of NR-011
    in one number: the form this project rejects is the one that fits better,
    and research 003 section 3.1 is why it is rejected anyway. The code is
    what keeps that choice visible in the output.
    """
    codes, entry = _run(lorentzian_constrained=False)
    assert "D_SPECTRUM_UNCONSTRAINED" in codes
    assert not entry.extension.constrained

    codes, entry = _run()
    assert "D_SPECTRUM_UNCONSTRAINED" not in codes
    assert entry.extension.constrained


# ------------------------------------------------ what the inversion could settle

@pytest.mark.slow
def test_a_noise_level_no_strength_can_reach_is_reported():
    """AC-018. The selected strength is then a fallback, not a selection.

    Declaring a noise a thousand times below anything present makes the
    discrepancy principle unsatisfiable at every strength, which is exactly
    the state a reader must not mistake for a selection.
    """
    codes, entry = _run(noise_source=[1e-9, 1e-9])
    assert "D_SPECTRUM_NOISE_UNREACHED" in codes
    assert not entry.branch("hole").noise_reached
    assert not entry.branch("electron").noise_reached


@pytest.mark.slow
def test_a_range_too_narrow_to_show_a_plateau_is_reported_as_unresolved():
    """AC-020. No run of the declared length means no count the data supports.

    Three strengths examined against a plateau of nine: the count may well be
    right, and the program still may not claim it.
    """
    codes, entry = _run(alpha_min=1e-12, alpha_max=1e-10, plateau_decades=9)
    assert "D_SPECTRUM_UNRESOLVED" in codes
    assert entry.unresolved
    assert all(branch.plateaus == () for branch in entry.branches)


# ------------------------------- the two states the design makes unreachable

def _entry(**branch_fields):
    """A spectrum record carrying one branch in a stated state."""
    grid = np.array([1.0, 2.0, 3.0])
    fields = dict(
        kind="electron", mu_grid_m2Vs=grid, density=np.zeros(3), peaks=(),
        alpha=1e-6, steps=(), plateaus=((3, 9),), noise_reached=True,
        negative_fraction=0.0,
    )
    fields.update(branch_fields)
    extension = spectrum.Extension(
        n_terms=6, amplitude_X=np.zeros(6), amplitude_Y=np.zeros(6),
        weight_hole=np.zeros(6), weight_electron=np.zeros(6),
        mobility_m2Vs=np.ones(6), cost=0.0, max_relative_residual=0.0,
        n_starts=12, n_starts_agreeing=12, constrained=True, at_bound=False,
    )
    return spectrum.TemperatureSpectrum(
        T_K=5.0, sigma_xx_zero=1.0, zero_field_records=9, extension=extension,
        branches=(spectrum.Branch(**fields),), noise=(1.0, 1.0),
        noise_source="residual", target_residual_norm=1.0,
        recombination_error=0.0,
        # the round trip of FR-079 is not what these two tests are about, so
        # it is set well inside AC-025 to keep its code out of the way
        roundtrip_rhoxx=0.0, roundtrip_rhoxy=0.0, roundtrip_tolerance=0.05,
    )


def test_a_wrong_signed_part_is_reported_never_repaired():
    """FR-071 and AC-024. NR-011 makes this unreachable; the code stays.

    With the constraint in force every separated part is non-negative by
    construction, so no sweep can produce this. The constraint can be switched
    off, and then it can -- research 003 section 3.1 measured `-77.7` where the
    true range was `+0.02` to `+0.50`. So the state has to remain reportable
    even though the default path cannot enter it.
    """
    codes = {d.code for d in diagnostics.spectrum_reading((_entry(negative_fraction=0.3),))}
    assert "D_SPECTRUM_NEGATIVE_PART" in codes

    clean = {d.code for d in diagnostics.spectrum_reading((_entry(),))}
    assert "D_SPECTRUM_NEGATIVE_PART" not in clean


def test_two_plateaus_in_one_branch_are_reported_as_ambiguous():
    """FR-073. The state the separation was introduced to remove.

    Before the separation, the count of the unseparated inversion moved from
    six to two across the regularisation range and this code was the normal
    outcome. It is now unreachable on the reference sweep, and a reader whose
    data puts a branch back into it must be told rather than handed whichever
    count the selected strength happened to give.
    """
    entry = _entry(plateaus=((2, 5), (6, 4)))
    found = diagnostics.spectrum_reading((entry,))
    codes = {d.code for d in found}
    assert "D_SPECTRUM_AMBIGUOUS" in codes
    assert entry.ambiguous

    where = next(d.where for d in found if d.code == "D_SPECTRUM_AMBIGUOUS")
    assert where["counts"] == "2/6", "both counts have to reach the reader"


def test_the_plateau_search_is_what_decides_between_those_two_states():
    """The unit under the two tests above, on the sequence that defines it."""
    from mbfit.core import spectrum as core

    assert core.plateaus([3] * 9, 3) == [(3, 9)]
    # longest first, so the count with the most support is named first
    assert core.plateaus([6] * 4 + [5] + [2] * 5, 3) == [(2, 5), (6, 4)]
    assert core.plateaus([6, 5, 4, 3, 2], 3) == []
