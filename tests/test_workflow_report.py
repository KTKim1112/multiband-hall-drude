"""Feature 004 -- what the reader receives. FR-091, FR-092. Gate 16.

The workflow itself takes minutes to run, so the tables and the page are tested
on a result built by hand. That also makes the tests say exactly which cell
each field lands in, which a real run would only exercise indirectly.

One test runs the command line end to end and is marked slow.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import math
import pathlib
import re

import numpy as np
import pytest

from mbfit import dataio, workflow, workflow_report
from mbfit.messages import REPORT_TEXT

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _group(T_K):
    B = np.linspace(-9.0, 9.0, 61)
    return dataio.TemperatureGroup(
        T_K=T_K, B_T=B, rhoxx_uohmcm=1.0 + 0.01 * B**2, rhoxy_uohmcm=0.05 * B,
        in_fit_window=np.ones(B.size, dtype=bool),
        n_records_dropped=0, n_mirror_interpolated=0, n_mirror_absent=0,
    )


def _candidate(n_hole, n_electron, rmse, **extra):
    fields = dict(
        n_hole=n_hole, n_electron=n_electron, rmse_rhoxx=rmse, rmse_rhoxy=rmse / 5,
        r2_rhoxx=0.99, r2_rhoxy=0.999, condition_number=150.0, spread=1e-7,
        weakest_share=0.1, at_bound=False, expired=False, n_starts=12, seconds=1.2,
        params=np.array([1.0, 1.0]), specs=("x",),
    )
    fields.update(extra)
    return workflow.Candidate(**fields)


def _carrier(name, kind, n, mu, share):
    return {"name": name, "kind": kind, "density_cm3": n, "mobility_cm2Vs": mu,
            "conduction_share": share, "mu_B_at_9T": mu * 1e-4 * 9.0}


def _result(mode="data", hostile_name="h1"):
    fit_outcome = workflow.TemperatureOutcome(
        T_K=5.0, mode=mode, n_hole=1, n_electron=1, grade="A",
        r2_rhoxx=0.9990, r2_rhoxy=0.9999, rmse_rhoxx=0.04, rmse_rhoxy=0.006,
        condition_number=250.0, spread=2e-7, seconds=81.0,
        bounds={"count": {"hole": 2, "electron": 2}, "window": {}},
        carriers=(_carrier(hostile_name, "hole", 6.0e20, 18000.0, 0.6),
                  _carrier("e1", "electron", 3.5e20, 19800.0, 0.4)),
        candidates=(_candidate(1, 1, 0.04),
                    _candidate(2, 2, float("inf"), expired=True, specs=())),
    )
    failing = workflow.TemperatureOutcome(
        T_K=120.0, mode=mode, n_hole=1, n_electron=1, grade="C",
        r2_rhoxx=0.816, r2_rhoxy=0.999, rmse_rhoxx=0.009, rmse_rhoxy=0.007,
        condition_number=1.3e4, spread=float("nan"), seconds=40.0,
        bounds={"count": {"hole": 1, "electron": 1}, "window": {}},
        carriers=(_carrier("h1", "hole", 3.0e21, 32.0, 0.49),
                  _carrier("e1", "electron", 1.5e21, 69.0, 0.51)),
        candidates=(_candidate(1, 1, 0.009, weakest_share=0.0001),),
        failed_gates=("earns",), escaped_window=("h1",),
        stop_reason=("fit_out_of_budget" if mode == "peaks" else ""),
    )
    dataset = dataio.Dataset(groups=(_group(5.0), _group(120.0)), n_records_dropped=0)
    return workflow.WorkflowResult(mode=mode, outcomes=(fit_outcome, failing),
                                   seconds=121.0, dataset=dataset, hall_polarity=1.0)


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ------------------------------------------------------------------ tables

def test_the_three_tables_are_written(tmp_path):
    written = workflow_report.write_tables(_result(), tmp_path)
    assert [p.name for p in written] == [
        workflow_report.SUMMARY, workflow_report.CARRIERS, workflow_report.CANDIDATES]
    for path in written:
        assert path.exists()


def test_the_summary_has_a_row_per_temperature_with_the_verdict(tmp_path):
    workflow_report.write_tables(_result(), tmp_path)
    rows = _rows(tmp_path / workflow_report.SUMMARY)
    assert [float(r["T(K)"]) for r in rows] == [5.0, 120.0]
    assert rows[0]["combination"] == "1h+1e" and rows[0]["grade"] == "A"
    assert rows[1]["gates_failed"] == "earns"
    assert rows[1]["outside_window"] == "h1"


def test_a_number_that_is_not_a_number_is_an_empty_cell(tmp_path):
    """data-model 004 section 2. NaN and infinity are never written as values."""
    workflow_report.write_tables(_result(), tmp_path)
    summary = _rows(tmp_path / workflow_report.SUMMARY)
    assert summary[1]["spread"] == ""
    candidates = _rows(tmp_path / workflow_report.CANDIDATES)
    expired = [r for r in candidates if r["out_of_budget"] == "True"]
    assert expired and expired[0]["RMSE_rhoxx(microohm_cm)"] == ""


def test_every_combination_tried_is_a_row(tmp_path):
    """FR-091. The combination table is what makes FR-084 checkable."""
    workflow_report.write_tables(_result(), tmp_path)
    candidates = _rows(tmp_path / workflow_report.CANDIDATES)
    assert len(candidates) == 3
    assert {(r["T(K)"], r["holes"], r["electrons"]) for r in candidates} == {
        ("5.0", "1", "1"), ("5.0", "2", "2"), ("120.0", "1", "1")}


def test_every_carrier_is_a_row_with_units_in_the_header(tmp_path):
    workflow_report.write_tables(_result(), tmp_path)
    carriers = _rows(tmp_path / workflow_report.CARRIERS)
    assert len(carriers) == 4
    assert "density(cm^-3)" in carriers[0] and "mobility(cm^2_Vs)" in carriers[0]


def test_a_better_undetermined_combination_is_a_column(tmp_path):
    """FR-085. Reported beside the verdict, in the table as on the page."""
    result = _result()
    flagged = dataclasses.replace(result.outcomes[0], undetermined_better="4h+2e",
                                  undetermined_ratio=1.44)
    result = dataclasses.replace(result, outcomes=(flagged, result.outcomes[1]))
    workflow_report.write_tables(result, tmp_path)
    rows = _rows(tmp_path / workflow_report.SUMMARY)
    assert rows[0]["undetermined_better"] == "4h+2e"
    assert float(rows[0]["undetermined_ratio"]) == 1.44
    assert rows[1]["undetermined_better"] == "" and rows[1]["undetermined_ratio"] == ""


def test_the_peaks_rule_records_why_its_loop_stopped(tmp_path):
    """Research 004 section 4.1. A bare iteration count hid a loop that never ran."""
    workflow_report.write_tables(_result(mode="peaks"), tmp_path)
    rows = _rows(tmp_path / workflow_report.SUMMARY)
    assert rows[1]["loop_stop"] == "fit_out_of_budget"
    assert rows[1]["count_rule"] == "peaks"


# -------------------------------------------------------------------- page

def test_the_page_fetches_nothing(tmp_path):
    """FR-092. It is sent by email and opened behind a firewall."""
    page = workflow_report.write_page(_result(), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    assert "http://" not in page.replace('xmlns="http://www.w3.org/2000/svg"', "") \
        .replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in page
    assert "<link" not in page
    assert not re.search(r"<script[^>]+src=", page)
    assert "@import" not in page


def test_the_verdict_comes_before_the_numbers(tmp_path):
    """FR-092. A reader shown the numbers first does not read the verdict."""
    page = workflow_report.write_page(_result(), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    assert page.index('id="h-verdict"') < page.index('id="h-curves"') \
        < page.index('id="h-params"') < page.index('id="h-cands"')


def test_the_page_carries_every_temperature_and_the_curves(tmp_path):
    page = workflow_report.write_page(_result(), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    data = json.loads(re.search(r"var D = (\{.*?\});\nvar T", page, re.S).group(1))
    assert [t["T"] for t in data["temperatures"]] == [5.0, 120.0]
    curve = data["temperatures"][0]["curve"]
    assert len(curve["B"]) == len(curve["xx"]) == len(curve["fxx"]) > 0


def _with_spectrum():
    """The 5 K outcome, carrying the spectrum and the window it became."""
    mu = list(np.logspace(2.0, 5.0, 40))
    result = _result()
    first = dataclasses.replace(
        result.outcomes[0],
        spectrum={
            "hole": {"mobility_cm2Vs": mu,
                     "weight": list(np.exp(-((np.log10(mu) - 4.2) / 0.2) ** 2)),
                     "peaks_cm2Vs": [15800.0]},
            "electron": {"mobility_cm2Vs": mu,
                         "weight": list(np.exp(-((np.log10(mu) - 3.9) / 0.2) ** 2)),
                         "peaks_cm2Vs": [8600.0]},
        },
        bounds={"count": {"hole": 2, "electron": 2},
                "window": {"hole": (640.0, 149000.0), "electron": (285.0, 93000.0)}},
    )
    return dataclasses.replace(result, outcomes=(first, result.outcomes[1]))


def test_the_page_carries_the_spectrum_that_bounded_the_search(tmp_path):
    """FR-110, FR-107. The count and the range came from somewhere, and the
    reader of the command line's own page can look at it rather than take it."""
    page = workflow_report.write_page(
        _with_spectrum(), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    data = json.loads(re.search(r"var D = (\{.*?\});\nvar T", page, re.S).group(1))
    hole = data["temperatures"][0]["spectrum"]["hole"]
    assert len(hole["mobility_cm2Vs"]) == len(hole["weight"]) == 40
    assert hole["peaks_cm2Vs"] == [15800.0]
    assert data["temperatures"][0]["window"]["electron"] == [285.0, 93000.0]
    assert data["temperatures"][1]["spectrum"] is None


def test_the_spectrum_is_folded_away_and_says_what_its_axis_is(tmp_path):
    """FR-110. The verdict stays what the page leads with, and a reader who
    takes the weight for a density reads a peak height as a carrier count."""
    page = workflow_report.write_page(
        _with_spectrum(), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    assert '<details class="fold"><summary id="s-spectrum">' in page
    assert page.index('id="h-verdict"') < page.index('id="s-spectrum"')
    # The label table is embedded with ensure_ascii, so it arrives escaped.
    def embedded(key):
        return json.dumps(REPORT_TEXT[key])[1:-1]
    assert embedded("spectrum_weight") in page
    assert embedded("spectrum_note") in page


def test_the_page_says_how_far_the_band_is_from_a_smooth_series(tmp_path):
    """FR-109, FR-107. The page of feature 005 measures it for a band the
    reader picks; a reader of the command line gets it for the band they ran."""
    two = workflow_report.payload(_result())
    assert two["roughness"] is None, "two temperatures have no curvature"

    result = _result()
    band = [dataclasses.replace(result.outcomes[0], T_K=T,
                                carriers=tuple(dict(c) for c in result.outcomes[0].carriers))
            for T in (5.0, 10.0, 15.0)]
    payload = workflow_report.payload(
        dataclasses.replace(result, outcomes=tuple(band), dataset=None))
    assert payload["roughness"] == pytest.approx(0.0, abs=1e-9), (
        "a band that does not bend at all is not rough")


def test_a_value_cannot_close_the_script_early(tmp_path):
    """A carrier name is data. `</script>` inside it must not end the page's code."""
    page = workflow_report.write_page(
        _result(hostile_name="</script><b>x"), tmp_path, REPORT_TEXT).read_text(encoding="utf-8")
    assert page.count("</script>") == 1


def test_no_value_in_the_page_is_nan():
    """JSON has no NaN, and a browser refuses the whole script over one."""
    body = workflow_report._embed(workflow_report.payload(_result()))
    assert "NaN" not in body and "Infinity" not in body
    json.loads(body.replace("<\\/", "</"))


def test_every_label_the_page_uses_is_in_the_message_table():
    """Article IV. A missing label shows as an empty heading, silently."""
    template = workflow_report._TEMPLATE
    keys = set(re.findall(r"\bT\.([a-z_]+[a-zA-Z0-9_]*)", template))
    keys |= set(re.findall(r'say\("[^"]+","([a-z_A-Z0-9]+)"\)', template))
    keys |= {k for group in re.findall(r"head\(\"[a-z-]+\", \[([^\]]+)\]", template)
             for k in re.findall(r'"([a-z_A-Z0-9]+)"', group)}
    for section in ("verdict", "curves", "params", "cands"):
        keys |= {f"{section}_heading", f"{section}_intro"}
    keys |= {f"grade_{g}" for g in ("A", "B", "C", "D", "dash")}
    keys |= {f"stop_{s}" for s in ("converged", "max_iterations",
                                   "fit_out_of_budget", "no_peaks")}
    missing = sorted(k for k in keys if k not in REPORT_TEXT)
    assert not missing, f"labels the page needs and messages.py lacks: {missing}"


def test_the_generator_itself_is_ascii():
    """Article IV. Korean arrives as an argument, never as a literal."""
    source = (ROOT / "mbfit" / "workflow_report.py").read_text(encoding="utf-8")
    assert all(ord(ch) < 128 for ch in source)


# ------------------------------------------------------------ command line

@pytest.mark.slow
def test_the_command_line_runs_a_mode_and_writes_the_page(tmp_path, capsys):
    """Gate 16 on the reference 5 K sweep. FR-080, FR-081."""
    from mbfit.cli import main

    document = json.loads((ROOT / "configs" / "synthetic_5K.json").read_text(encoding="utf-8"))
    document["spectrum"] = {"enabled": True, "lorentzian_terms": 6,
                            "lorentzian_multi_start": 12, "mu_min_cm2Vs": 100.0}
    document["output"] = {"make_plots": False}
    config = tmp_path / "config.json"
    config.write_text(json.dumps(document), encoding="utf-8")
    out = tmp_path / "out"

    code = main(["--data", str(ROOT / "tests" / "data" / "synthetic_5K.csv"),
                 "--config", str(config), "--out", str(out), "--count", "data"])
    assert code == 0
    for name in (workflow_report.SUMMARY, workflow_report.CARRIERS,
                 workflow_report.CANDIDATES, workflow_report.PAGE):
        assert (out / name).exists(), name

    # FR-110. The spectrum that set the bound reaches the page the command
    # line writes, from a real run and not from a result built by hand.
    page = (out / workflow_report.PAGE).read_text(encoding="utf-8")
    data = json.loads(re.search(r"var D = (.*?);" + chr(10) + "var T", page, re.S).group(1))
    hole = data["temperatures"][0]["spectrum"]["hole"]
    assert len(hole["mobility_cm2Vs"]) == len(hole["weight"]) > 50
    assert hole["peaks_cm2Vs"]

    printed = capsys.readouterr().out
    # `3h+2e` is what the procedure answers on the synthetic 5 K sweep, which
    # is generated from three carriers of each sign. It read `2h+2e` while the
    # sweep was a measured one.
    assert "data" in printed and "3h+2e" in printed
    assert REPORT_TEXT["count_notice_data"] in printed
    # FR-107, FR-109. One sweep is not a band, and the command line says so
    # rather than printing a number that would mean nothing.
    assert REPORT_TEXT["roughness_none"] in printed
