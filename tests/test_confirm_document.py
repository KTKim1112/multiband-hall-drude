"""FR-107 and FR-112. What the page does, a document can ask for.

The page lets a reader pin a carrier count and then couple a band across
temperature. The first has had a document form since FR-090 (`fixed_counts`);
the second had none, because the coupling runs under a strategy the procedure
never selects for itself. So a reader could produce, on the page, an answer
they could not reproduce on the command line -- and FR-112 makes the confirmed
answer reproducible, which turns that gap into a defect rather than an
omission.

These tests are the library half of the confirm of FR-112. If they pass, the
document written beside a confirmed answer really does reproduce it.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import workflow
from mbfit.config import resolve
from mbfit.core.errors import MbfitError

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERIES = ROOT / "tests" / "data" / "synthetic_series.csv"
BAND = "5-40"


def _document():
    document = json.loads(
        (ROOT / "configs" / "synthetic_5K.json").read_text(encoding="utf-8"))
    document["spectrum"] = {"enabled": True, "lorentzian_terms": 6,
                            "lorentzian_multi_start": 6, "mu_min_cm2Vs": 100.0}
    document["output"] = {"make_plots": False}
    return document


def _pinned(**workflow_settings):
    document = _document()
    document["workflow"] = {"fixed_counts": {BAND: [2, 2]}, **workflow_settings}
    return document


def _parameters(result):
    """Every carrier of every sweep, in the order the report writes them."""
    return {
        item.T_K: [(c["name"], c["density_cm3"], c["mobility_cm2Vs"])
                   for c in item.carriers]
        for item in result.outcomes
    }


@pytest.mark.slow
def test_a_document_can_ask_for_the_coupling_the_page_offers():
    """FR-107. The page's two moves, done by `analyse` alone from a document.

    Compared against the same band coupled the way the page does it: pin the
    count, then hand the pinned outcomes to `smooth_band`. The document route
    must reach the same answer, or the document written beside a confirmed
    answer does not reproduce it.
    """
    pinned = workflow.analyse(SERIES, _pinned(), mode="data")
    assert {item.label for item in pinned.outcomes} == {"2h+2e"}

    # the page's route: couple the pinned band directly
    settings = dict(resolve(_pinned()).workflow)
    equivalence = float(resolve(_pinned()).acceptance["cost_equivalence"])
    by_hand, _lam = workflow.smooth_band(
        _pinned(), list(pinned.outcomes), list(pinned.dataset.groups),
        settings, equivalence, "normal")
    by_hand = [workflow.with_fit_quality(item, group, pinned.hall_polarity)
               for item, group in zip(by_hand, pinned.dataset.groups)]

    # the document's route: one call, no page
    from_document = workflow.analyse(
        SERIES, _pinned(smooth_band=[{"range": BAND, "strength": "normal"}]),
        mode="data")

    wanted = _parameters(workflow.WorkflowResult(
        mode="data", outcomes=tuple(by_hand), seconds=0.0))
    got = _parameters(from_document)
    assert sorted(got) == sorted(wanted)
    for T_K in wanted:
        for (name, n, mu), (name2, n2, mu2) in zip(wanted[T_K], got[T_K]):
            assert name == name2, T_K
            assert n2 == pytest.approx(n, rel=1e-9), (T_K, name)
            assert mu2 == pytest.approx(mu, rel=1e-9), (T_K, name)


@pytest.mark.slow
def test_a_coupling_asked_of_a_document_changes_the_answer_it_couples():
    """The guard above is worth nothing if the coupling does nothing. This
    measures that the coupled answer differs from the pinned one it came from,
    so that agreement between the two routes is agreement about something."""
    pinned = workflow.analyse(SERIES, _pinned(), mode="data")
    coupled = workflow.analyse(
        SERIES, _pinned(smooth_band=[{"range": BAND, "strength": "strong"}]),
        mode="data")
    before = _parameters(pinned)
    after = _parameters(coupled)
    moved = max(
        abs(np.log(b[2]) - np.log(a[2]))
        for T_K in before for a, b in zip(before[T_K], after[T_K])
    )
    assert moved > 1e-6, "a strong coupling that moves nothing is not a coupling"


class _Sweep:
    """The little `_apply_smooth_bands` reads before it decides to refuse.

    Built by hand rather than fitted: the refusals are about the shape of the
    band, and running the procedure to reach them would cost minutes per
    temperature for an answer the shape alone settles.
    """

    def __init__(self, T_K, n_hole, n_electron):
        self.T_K = float(T_K)
        self.n_hole = n_hole
        self.n_electron = n_electron
        self.carriers = ({"name": "h1"},) * (n_hole + n_electron)


def _refuse(rows, band):
    settings = {"smooth_band": [dict(band, low=float(band["range"].split("-")[0]),
                                     high=float(band["range"].split("-")[-1]))]}
    with pytest.raises(MbfitError) as raised:
        workflow._apply_smooth_bands({}, rows, (), settings, 1.0, 1.0)
    return raised.value


def test_a_band_of_two_sweeps_is_refused_rather_than_coupled():
    """A curvature needs three points. Coupling two sweeps would report a
    constraint that did nothing."""
    rows = [_Sweep(5, 2, 2), _Sweep(20, 2, 2), _Sweep(40, 2, 2)]
    error = _refuse(rows, {"range": "5-20", "strength": "normal"})
    assert error.code == "E_CONFIG_BAD_VALUE"
    assert "three" in error.detail["expected"]


def test_a_band_whose_sweeps_do_not_share_a_count_is_refused():
    """There is nothing to couple across sweeps with different carrier sets,
    and `fixed_counts` is what a reader is told to reach for."""
    rows = [_Sweep(5, 2, 2), _Sweep(20, 1, 1), _Sweep(40, 2, 2)]
    error = _refuse(rows, {"range": "5-40", "strength": "normal"})
    assert error.code == "E_CONFIG_BAD_VALUE"
    assert "fixed_counts" in error.detail["expected"]


def test_a_document_without_a_band_couples_nothing():
    """Off unless asked for, as FR-109 requires of the coupling on the page."""
    assert resolve(_document()).workflow["smooth_band"] == []
    rows = [_Sweep(5, 2, 2), _Sweep(20, 2, 2), _Sweep(40, 2, 2)]
    assert workflow._apply_smooth_bands({}, rows, (), {"smooth_band": []},
                                        1.0, 1.0) is rows
