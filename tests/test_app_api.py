"""Feature 005 -- the server, through its endpoints. FR-097 to FR-105. Gate 17.

The analysis itself is replaced by a stand-in that reports progress, honours
the stop and returns a known result, because the real one takes minutes and
features 001 to 004 already test it (FR-107). What is tested here is everything
around it: codes, the stop, what is kept, and that the downloads are the files
the command line's own writers produce.

One test runs the real analysis on one reference file and is marked slow.
"""

from __future__ import annotations

import copy
import io
import json
import pathlib
import threading
import time
import zipfile

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient              # noqa: E402

from app import errors, runner                         # noqa: E402
from app.main import app                               # noqa: E402
from mbfit import dataio, workflow, workflow_report     # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: Sweeps in the shape an instrument writes them, written by
#: `tests/data/make_synthetic.py`. Nothing here is measured.
EXAMPLE = ROOT / "tests" / "data" / "uploads"
SWEEP = "B,rho_xx,rho_xy\n" + "".join(
    f"{b:.2f},{1 + 0.01 * b * b:.5f},{0.05 * b:.5f}\n" for b in np.linspace(-9, 9, 37))


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_answers_so_the_page_can_tell_the_program_is_there(client):
    """FR-108. The page asks this and nothing else to decide it is alone."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["version"]


def _upload(client, *named):
    files = [("files", (name, text.encode("utf-8"), "text/csv")) for name, text in named]
    response = client.post("/api/files", files=files)
    assert response.status_code == 200, response.json()
    return response.json()["files"]


def _mapping(preview):
    proposal = preview["proposal"]
    return {"file_id": preview["file_id"], "B": proposal["B"], "rhoxx": proposal["rhoxx"],
            "rhoxy": proposal["rhoxy"], "T_column": proposal["T_column"],
            "T_K": proposal["T_from_name"]}


def _wait(client, job_id, states=("succeeded", "failed", "stopped"), timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = client.get(f"/api/jobs/{job_id}").json()
        if view["state"] in states:
            return view
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never reached {states}: {view}")


def _outcome(T_K, mode="data", answered=True):
    carriers = ({"name": "h1", "kind": "hole", "density_cm3": 1e21, "mobility_cm2Vs": 500.0,
                 "conduction_share": 0.5, "mu_B_at_9T": 0.45},
                {"name": "e1", "kind": "electron", "density_cm3": 1e21, "mobility_cm2Vs": 400.0,
                 "conduction_share": 0.5, "mu_B_at_9T": 0.36})
    return workflow.TemperatureOutcome(
        T_K=T_K, mode=mode, n_hole=1, n_electron=1, grade="A" if answered else "-",
        r2_rhoxx=0.99, r2_rhoxy=0.999, rmse_rhoxx=0.01, rmse_rhoxy=0.001,
        condition_number=100.0, spread=1e-8, seconds=1.0, bounds={},
        carriers=carriers if answered else ())


class StandIn:
    """Replaces `workflow.analyse`. Holds at a gate until released, so a test
    can stop it at a known point."""

    def __init__(self):
        self.release = threading.Event()
        self.calls = []

    def __call__(self, path, document, mode=None, hooks=None):
        self.calls.append((path, document, mode))
        config = runner.resolve(document)
        dataset = dataio.load_dataset(path, config)
        outcomes = []
        for index, group in enumerate(dataset.groups):
            hooks.report(stage="temperature", T_K=group.T_K, index=index,
                         total=len(dataset.groups))
            if index == 1:
                while not self.release.is_set():
                    if hooks.stop():
                        raise workflow.Cancelled(outcomes, dataset, 1.0)
                    time.sleep(0.01)
            hooks.check()
            hooks.report(stage="search", T_K=group.T_K, holes=1, electrons=1)
            # The peaks rule's stand-in finds nothing to fit at 20 K.
            outcomes.append(_outcome(group.T_K, mode, answered=not (mode == "peaks" and group.T_K == 20.0)))
        return workflow.WorkflowResult(mode=mode, outcomes=tuple(outcomes), seconds=0.1,
                                       dataset=dataset, hall_polarity=1.0)


@pytest.fixture()
def stand_in(monkeypatch):
    fake = StandIn()
    monkeypatch.setattr(runner.workflow, "analyse", fake)
    return fake


def _three(client):
    return [_mapping(p) for p in _upload(client, ("5K.csv", SWEEP), ("10K.csv", SWEEP),
                                         ("20K.csv", SWEEP))]


# ------------------------------------------------------------------ codes

def test_every_code_the_server_raises_is_declared():
    """FR-105. A code the page has no message for shows as nothing."""
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").glob("*.py"))
    import re
    from mbfit.core.errors import ERROR_CODES
    raised = set(re.findall(r'"(E_[A-Z_]+)"', source))
    # The server may name a library code to translate it into one of its own --
    # a coupled fit that ran out of its budget is not "no start could fit".
    known = set(errors.APP_CODES) | set(ERROR_CODES) | {"E_NOT_FOUND"}
    assert raised <= known, raised - known


def test_the_page_has_a_message_for_every_code():
    """FR-105. A code with no message shows as nothing -- in either language.

    Checking only one of them would let the second language fall behind
    silently, which is the way a translation usually rots.
    """
    from mbfit.core.errors import ERROR_CODES
    wanted = (*errors.APP_CODES, *ERROR_CODES)
    for language in ("ko", "en"):
        path = ROOT / "frontend" / "src" / "text" / f"{language}.ts"
        if not path.exists():
            pytest.skip("frontend not present")
        text = path.read_text(encoding="utf-8")
        missing = [code for code in wanted if code not in text]
        assert not missing, f"{language}: {missing}"


def test_no_sentence_leaves_the_server(client):
    """FR-105. A malformed request is a code and the fields it concerns."""
    response = client.post("/api/analyses", json={"files": "not a list"})
    assert response.status_code == 422
    assert response.json() == {"code": "E_REQUEST_INVALID", "params": {"fields": ["body.files"]}}


def test_the_count_rule_defaults_to_the_data_and_refuses_anything_else(client, stand_in):
    """FR-099. The rule that needs no evidence beyond the sweep is the default."""
    stand_in.release.set()
    mappings = _three(client)
    job_id = client.post("/api/analyses", json={"files": mappings}).json()["job_id"]
    _wait(client, job_id)
    assert stand_in.calls[-1][2] == "data"
    response = client.post("/api/analyses", json={"files": _three(client), "count": "best"})
    assert response.json() == {"code": "E_COUNT_RULE_UNKNOWN", "params": {"count": "best"}}


def test_a_duplicate_temperature_is_refused_before_a_job_starts(client, stand_in):
    one, two = _upload(client, ("5K.csv", SWEEP), ("5 K repeat.csv", SWEEP))
    response = client.post("/api/analyses", json={"files": [_mapping(one), _mapping(two)],
                                                  "count": "data"})
    assert response.status_code == 422
    assert response.json()["code"] == "E_TEMPERATURE_DUPLICATE"
    assert not stand_in.calls


def test_an_unknown_job_is_a_404_with_a_code(client):
    response = client.get("/api/jobs/nope")
    assert response.status_code == 404 and response.json()["code"] == "E_JOB_NOT_FOUND"


# ------------------------------------------------------------ running

def test_an_analysis_runs_in_the_background_and_reports_progress(client, stand_in):
    """FR-097. The request returns before the analysis does."""
    job = client.post("/api/analyses", json={"files": _three(client), "count": "data"})
    assert job.status_code == 202
    job_id = job.json()["job_id"]
    view = _wait(client, job_id, states=("running",))
    deadline = time.monotonic() + 10
    while view["progress"].get("index") != 1 and time.monotonic() < deadline:
        view = client.get(f"/api/jobs/{job_id}").json()
    assert view["state"] == "running"
    assert view["progress"]["stage"] == "temperature" and view["progress"]["total"] == 3
    stand_in.release.set()
    done = _wait(client, job_id)
    assert done["state"] == "succeeded"
    assert [t["T"] for t in done["result"]["temperatures"]] == [5.0, 10.0, 20.0]


def test_a_stop_keeps_what_finished_and_is_not_a_failure(client, stand_in):
    """FR-098."""
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    deadline = time.monotonic() + 10
    while client.get(f"/api/jobs/{job_id}").json()["progress"].get("index") != 1:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert client.post(f"/api/jobs/{job_id}/stop").status_code == 202
    view = _wait(client, job_id)
    assert view["state"] == "stopped" and view["error"] is None
    assert [t["T"] for t in view["result"]["temperatures"]] == [5.0]


def test_the_symmetrisation_switches_stay_off_unless_turned_on(client, stand_in):
    """FR-100."""
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    document = stand_in.calls[-1][1]
    assert not document["preprocess"].get("symmetrize_rhoxx")
    assert not document["preprocess"].get("antisymmetrize_rhoxy")

    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data",
                                                "symmetrize_rhoxx": True}).json()["job_id"]
    _wait(client, job_id)
    assert stand_in.calls[-1][1]["preprocess"]["symmetrize_rhoxx"] is True


def test_the_preliminary_model_is_named_and_can_be_replaced(client, stand_in):
    """FR-102."""
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    view = _wait(client, job_id)
    assert [c["name"] for c in view["preliminary"]] == ["h1", "h2", "e1", "e2"]

    supplied = {"schema_version": "1.0", "carriers": [
        {"name": "hx", "kind": "hole", "density": {"init": 1e21, "min": 1e15, "max": 1e24},
         "mobility": {"init": 300.0, "min": 1.0, "max": 1e6}},
        {"name": "ex", "kind": "electron", "density": {"init": 1e21, "min": 1e15, "max": 1e24},
         "mobility": {"init": 300.0, "min": 1.0, "max": 1e6}}]}
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data",
                                                "document": supplied}).json()["job_id"]
    view = _wait(client, job_id)
    assert [c["name"] for c in view["preliminary"]] == ["hx", "ex"]


def test_a_bad_document_fails_the_request_not_the_job(client, stand_in):
    response = client.post("/api/analyses", json={"files": _three(client), "count": "data",
                                                  "document": {"schema_version": "9"}})
    assert response.status_code == 422
    assert response.json()["code"].startswith("E_CONFIG_")
    assert not stand_in.calls


# ------------------------------------------------------------ showing

def test_downloads_are_the_command_line_files(client, stand_in, tmp_path):
    """FR-104. The same writers, so the same bytes."""
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    from app.jobs import store
    result = store.get(job_id).context["analysis"]
    workflow_report.write_tables(result, tmp_path)
    workflow_report.write_page(result, tmp_path, runner.REPORT_TEXT)

    page = client.get(f"/api/jobs/{job_id}/report.html")
    assert page.status_code == 200
    assert page.content == (tmp_path / workflow_report.PAGE).read_bytes()

    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/jobs/{job_id}/tables.zip").content))
    for name in (workflow_report.SUMMARY, workflow_report.CARRIERS, workflow_report.CANDIDATES):
        assert archive.read(name) == (tmp_path / name).read_bytes(), name


def test_nothing_downloads_before_the_analysis_succeeds(client, stand_in):
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    response = client.get(f"/api/jobs/{job_id}/report.html")
    assert response.status_code == 409 and response.json()["code"] == "E_JOB_NOT_FINISHED"
    stand_in.release.set()
    _wait(client, job_id)


def test_a_precise_check_needs_a_fit_to_resample(client, stand_in):
    """FR-101. Both count rules end in a fit; a temperature with none is refused."""
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "peaks"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/precise", json={"T_K": 20.0})
    assert response.json()["code"] == "E_PRECISE_NO_ANSWER"
    assert client.post(f"/api/jobs/{job_id}/precise", json={"T_K": 5.0}).status_code == 202


def test_a_precise_check_for_an_absent_temperature_is_refused(client, stand_in):
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/precise", json={"T_K": 7.0})
    assert response.json()["code"] == "E_PRECISE_UNKNOWN_TEMPERATURE"


def test_a_refit_answers_at_the_count_the_reader_chose(client, stand_in):
    """FR-109. The reader overrides the count at one temperature only.

    The analysis is not run again: the refit rebuilds the spectrum for that one
    sweep and calls the same routine the command line uses for
    `workflow.fixed_counts`, so the two answer alike.
    """
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    started = client.post(f"/api/jobs/{job_id}/recount",
                          json={"temperatures": [5.0], "holes": 1, "electrons": 1})
    assert started.status_code == 202
    view = _wait(client, started.json()["job_id"], timeout=180)
    assert view["state"] == "succeeded", view["error"]
    # The shape an analysis result has, so one temperature and a band are the
    # same shape and the page draws both with the components it already has.
    answer = view["result"]["temperatures"]
    assert len(answer) == 1
    assert answer[0]["label"] == "1h+1e"
    assert answer[0]["T"] == 5.0
    assert len(answer[0]["carriers"]) == 2
    assert answer[0]["curve"] is not None and answer[0]["grade"]


def test_a_refit_holds_a_whole_band_to_one_count(client, stand_in):
    """FR-109 and FR-090. A series needs one carrier set across the band, so the
    band is what the reader pins; a single sweep is the band of length one."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    started = client.post(f"/api/jobs/{job_id}/recount",
                          json={"temperatures": [5.0, 10.0, 20.0],
                                "holes": 1, "electrons": 1})
    assert started.status_code == 202
    view = _wait(client, started.json()["job_id"], timeout=420)
    assert view["state"] == "succeeded", view["error"]
    rows = view["result"]["temperatures"]
    assert [row["T"] for row in rows] == [5.0, 10.0, 20.0]
    assert {row["label"] for row in rows} == {"1h+1e"}, "one carrier set across the band"
    # FR-109. The page draws the refit beside the procedure's answer in the
    # trends and in the carrier table, so every sweep of the band has to carry
    # its carriers and its model curve, not only its verdict.
    for row in rows:
        assert len(row["carriers"]) == 2, row["T"]
        assert all(c["n"] and c["mu"] for c in row["carriers"]), row["T"]
        assert row["curve"] is not None and row["curve"]["fxx"], row["T"]


def test_a_count_that_will_not_fit_is_named_and_not_passed_off_as_a_refit(
        client, stand_in, monkeypatch):
    """FR-109, amended. A pin the fit cannot honour is said out loud.

    `_refit_at` answers with nothing when no starting point finishes inside the
    budget. It used to answer with the outcome it had been given -- the very
    count the reader was overriding -- which reads as a refit that succeeded,
    and would carry that count into the confirmed document as though the
    procedure had met it. Measured cause: one start of a six-carrier fit takes
    231 s at 70 K against the 2.5 s the search allowed it.
    """
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    was = {t["T"]: t["label"]
           for t in client.get(f"/api/jobs/{job_id}").json()["result"]["temperatures"]}

    monkeypatch.setattr(runner.workflow, "_refit_at", lambda *a, **k: None)
    started = client.post(f"/api/jobs/{job_id}/recount",
                          json={"temperatures": [5.0, 10.0], "holes": 3, "electrons": 3})
    assert started.status_code == 202
    view = _wait(client, started.json()["job_id"], timeout=120)
    assert view["state"] == "succeeded", view["error"]

    answer = view["result"]
    assert answer["unheld"] == [5.0, 10.0], "the sweeps the count would not fit at"
    assert [t["label"] for t in answer["temperatures"]] == [was[5.0], was[10.0]], (
        "the procedure's own answer stands where the pin could not be applied")


def test_a_refit_before_the_analysis_has_finished_is_refused(client, stand_in):
    """FR-109. There is no verdict to override yet, and no table to refit from."""
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    response = client.post(f"/api/jobs/{job_id}/recount",
                           json={"temperatures": [5.0], "holes": 2, "electrons": 2})
    assert response.status_code == 409 and response.json()["code"] == "E_JOB_NOT_FINISHED"
    stand_in.release.set()
    _wait(client, job_id)


def test_a_refit_at_an_absent_temperature_is_refused(client, stand_in):
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/recount",
                           json={"temperatures": [5.0, 7.0], "holes": 2, "electrons": 2})
    assert response.json()["code"] == "E_PRECISE_UNKNOWN_TEMPERATURE"


def _refit(client, job_id, temperatures, holes=1, electrons=1, timeout=600):
    """A finished refit of a band, which is what a coupling is asked of."""
    started = client.post(f"/api/jobs/{job_id}/recount",
                          json={"temperatures": temperatures,
                                "holes": holes, "electrons": electrons})
    assert started.status_code == 202, started.json()
    refit = started.json()["job_id"]
    view = _wait(client, refit, timeout=timeout)
    assert view["state"] == "succeeded", view["error"]
    return refit, view["result"]


def test_a_coupling_needs_three_temperatures(client, stand_in):
    """FR-025. Second-order curvature is defined by three points; with two there
    is nothing for the penalty to act on, so the request is refused rather than
    quietly ignored."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    short, _ = _refit(client, job_id, [5.0, 10.0])
    response = client.post(f"/api/jobs/{short}/smooth", json={"strength": "normal"})
    assert response.json()["code"] == "E_SMOOTHING_TOO_FEW"

    band, _ = _refit(client, job_id, [5.0, 10.0, 20.0])
    unknown = client.post(f"/api/jobs/{band}/smooth", json={"strength": "very"})
    assert unknown.json()["code"] == "E_SMOOTHING_UNKNOWN"


def test_a_coupling_is_refused_of_anything_but_a_finished_refit(client, stand_in):
    """FR-109. The coupling acts on a band already held to one count. Asked of
    the analysis itself there is no such band, and the reader is told that
    rather than shown an internal fault."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/smooth", json={"strength": "normal"})
    assert response.status_code == 409
    assert response.json()["code"] == "E_SMOOTH_NO_BAND"


def test_a_refit_answers_before_any_coupling_is_asked_for(client, stand_in):
    """FR-109, amended 2026-09-19. The refit and the coupling were one request
    that answered only when both had finished. A coupling over a long band
    takes far longer than the refits it follows -- measured at 3061 s for
    thirteen sweeps -- so asking for one withheld refits that were already
    complete, and the page did nothing for hours.
    """
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    _, answer = _refit(client, job_id, [5.0, 10.0, 20.0])
    assert [row["T"] for row in answer["temperatures"]] == [5.0, 10.0, 20.0]
    assert answer["roughness"] is not None, "the roughness comes free with the band"
    assert answer["smoothing"] is None, (
        "a refit must answer on its own; the coupling is asked for separately")


def test_a_band_reports_its_roughness_and_what_a_coupling_costs(client, stand_in):
    """FR-025 and FR-109. The roughness comes free with the band; the coupling
    is optional, asked of the finished refit, and its price is reported per
    temperature."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    band, answer = _refit(client, job_id, [5.0, 10.0, 20.0])
    assert answer["roughness"] is not None, "three sweeps of one count have a roughness"

    started = client.post(f"/api/jobs/{band}/smooth", json={"strength": "normal"})
    assert started.status_code == 202
    view = _wait(client, started.json()["job_id"], timeout=600)
    assert view["state"] == "succeeded", view["error"]
    coupled = view["result"]
    assert coupled["strength"] == "normal"
    assert coupled["lambda"] > 0
    assert [row["T"] for row in coupled["temperatures"]] == [5.0, 10.0, 20.0]
    # the coupled answer keeps the count it was pinned to
    assert {row["label"] for row in coupled["temperatures"]} == {"1h+1e"}
    # and is drawn as its own set beside the other two, so it carries the same
    # things they do.
    for row in coupled["temperatures"]:
        assert len(row["carriers"]) == 2, row["T"]
        assert row["curve"] is not None and row["curve"]["fxy"], row["T"]


def test_a_band_without_a_coupling_still_reports_its_roughness(client, stand_in):
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    started = client.post(f"/api/jobs/{job_id}/recount",
                          json={"temperatures": [5.0, 10.0, 20.0],
                                "holes": 1, "electrons": 1})
    view = _wait(client, started.json()["job_id"], timeout=600)
    assert view["state"] == "succeeded", view["error"]
    assert view["result"]["smoothing"] is None
    assert view["result"]["roughness"] is not None


@pytest.mark.parametrize(
    "temperatures,holes,electrons",
    [([5.0], 0, 0), ([5.0], 5, 4), ([5.0], -1, 2), ([], 2, 2)],
)
def test_a_refit_at_a_count_no_sweep_determines_is_refused(
        client, stand_in, temperatures, holes, electrons):
    """AC-036. The search reaches four carriers per sign; a reader pinning by
    hand reaches the same and no further. A band of no temperatures pins
    nothing, and must not pass as though it had."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/recount",
                           json={"temperatures": temperatures, "holes": holes,
                                 "electrons": electrons})
    assert response.json()["code"] == "E_RECOUNT_INVALID"


def test_a_precise_check_runs_and_can_be_stopped(client, stand_in, monkeypatch):
    """FR-101. Progress per resample; a stop keeps nothing."""
    stand_in.release.set()
    job_id = client.post("/api/analyses", json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    started = client.post(f"/api/jobs/{job_id}/precise", json={"T_K": 5.0})
    assert started.status_code == 202
    precise_id = started.json()["job_id"]
    deadline = time.monotonic() + 60
    while True:
        view = client.get(f"/api/jobs/{precise_id}").json()
        if view["progress"].get("done", 0) >= 1 or view["state"] != "running":
            break
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert view["progress"]["stage"] == "resample"
    client.post(f"/api/jobs/{precise_id}/stop")
    view = _wait(client, precise_id, timeout=60)
    assert view["state"] == "stopped" and view["result"] is None


# -------------------------------------------------------------- the real thing

# ------------------------------------------------------- confirming, FR-112

def _analysed(document: dict):
    """A finished analysis job carrying the document it ran on, and no more.

    `document_for_confirm` reads exactly that, so the settings it carries
    forward can be checked without spending minutes on a real analysis.
    """
    from app.jobs import SUCCEEDED, Job
    return Job(job_id="parent", kind="analysis", state=SUCCEEDED,
               context={"document": copy.deepcopy(document)})


def _confirmed_workflow(declared: dict, fixed_counts: dict, smooth_band=()):
    document = {"schema_version": "1.0",
                "columns": dict(runner.tables.COLUMNS),
                "carriers": copy.deepcopy(list(runner.PRELIMINARY_CARRIERS)),
                "workflow": dict(declared, count="data")}
    made = runner.document_for_confirm(_analysed(document), fixed_counts,
                                       list(smooth_band))
    return made["workflow"]


def test_confirming_keeps_what_the_readers_own_document_pinned_elsewhere():
    """FR-112. An adjustment covers the sweeps it names and leaves the rest.

    The two settings used to be replaced outright, so a reader whose own
    configuration pinned 80 to 120 K, and who then adjusted 5 K on the page,
    confirmed an answer in which 80 to 120 K was no longer pinned at all. The
    analysis had run under that pin and the confirmation had not: the confirmed
    answer could differ from the one being confirmed at a sweep nobody touched.
    """
    work = _confirmed_workflow({"fixed_counts": {"80-120": [1, 1]}},
                               {"5": [2, 2]})
    assert work["fixed_counts"] == {"80-120": [1, 1], "5": [2, 2]}


def test_an_adjustment_beats_the_band_the_document_pinned_around_it():
    """FR-090. The narrowest range covering a sweep supplies its count.

    Both survive into the document and `workflow.count_for` chooses, so the
    merge has nothing to decide and the page's one-temperature pin wins where
    the two meet.
    """
    work = _confirmed_workflow({"fixed_counts": {"5-40": [2, 2]}},
                               {"20": [3, 2]})
    assert work["fixed_counts"] == {"5-40": [2, 2], "20": [3, 2]}
    pinned = workflow.pinned_counts(work["fixed_counts"])
    assert workflow.count_for(20.0, pinned) == (3, 2)
    assert workflow.count_for(5.0, pinned) == (2, 2)


def test_an_adjustment_inside_a_declared_band_ends_that_band():
    """A band half adjusted is not one series -- the rule the page follows.

    A coupling is refused unless its sweeps share a count, so a declared band
    that an adjustment lands inside would either fail the confirm outright or
    couple a sweep the reader had just pulled out of it.
    """
    work = _confirmed_workflow(
        {"smooth_band": [{"range": "5-40", "strength": "normal"}]},
        {"20": [3, 2]})
    assert work["smooth_band"] == []


def test_a_band_the_document_declared_away_from_the_adjustment_survives():
    work = _confirmed_workflow(
        {"smooth_band": [{"range": "80-120", "strength": "weak"}]},
        {"5": [2, 2]})
    assert work["smooth_band"] == [{"range": "80-120", "strength": "weak"}]


def test_a_band_asked_for_again_is_the_readers_and_not_the_documents():
    """The reader coupled the same range at a different strength; theirs wins,
    and it appears once rather than twice."""
    work = _confirmed_workflow(
        {"smooth_band": [{"range": "5-40", "strength": "weak"}]},
        {"5": [2, 2], "20": [2, 2], "40": [2, 2]},
        [{"range": "5-40", "strength": "strong"}])
    assert work["smooth_band"] == [{"range": "5-40", "strength": "strong"}]


def test_the_table_that_travels_carries_the_model_beside_the_measurement(tmp_path):
    """The reader already has their own sweeps, so handing them back unchanged
    is of no use. The fitted curve goes in the same table, at the same field
    and temperature.

    Built from a real dataset and a made-up answer: what is under test is the
    alignment and the columns, not the fit, and a fit would take minutes to
    say the same thing.
    """
    import types

    from mbfit import config as cfg, dataio

    source = ROOT / "tests" / "data" / "synthetic_small.csv"
    document = json.loads((ROOT / "configs" / "example_1e1h.json").read_text("utf-8"))
    config = cfg.resolve(document)
    dataset = dataio.load_dataset(source, config)

    carriers = [{"name": "h1", "kind": "hole", "density_cm3": 5e20,
                 "mobility_cm2Vs": 9000.0, "conduction_share": 0.6},
                {"name": "e2", "kind": "electron", "density_cm3": 4e20,
                 "mobility_cm2Vs": 7000.0, "conduction_share": 0.4}]
    result = types.SimpleNamespace(
        dataset=dataset, hall_polarity=1.0,
        outcomes=[types.SimpleNamespace(T_K=g.T_K, carriers=carriers)
                  for g in dataset.groups])

    path = tmp_path / runner.COMBINED
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    before = dataio.read_table(path, config)

    runner.add_model_to_combined(path, result)
    table = pd.read_csv(path)

    for column in ("rhoxx_fitted(microohm_cm)", "rhoxx_residual(microohm_cm)",
                   "rhoxy_fitted(microohm_cm)", "rhoxy_residual(microohm_cm)"):
        assert column in table.columns, column

    # Nothing was preprocessed and no field range was declared, so the columns
    # that would only repeat the row are not written.
    for column in ("in_fit_window", "rhoxx_measured(microohm_cm)",
                   "rhoxy_measured(microohm_cm)"):
        assert column not in table.columns, f"{column} repeats what is already there"

    # NR-013. The file is still what `--data` reads to reproduce the run: the
    # four declared columns are untouched and the rest is never looked at.
    after = dataio.read_table(path, config)
    assert after.equals(before), "the reproduction input changed"

    # The model belongs to the row it is written on, not to the row order.
    group = dataset.groups[1]
    row = table[(table["T(K)"] == group.T_K) & (table["B(T)"] == group.B_T[3])]
    assert len(row) == 1
    expected_xx, expected_xy = workflow._model_of(group, carriers, 1.0)
    assert row["rhoxx_fitted(microohm_cm)"].iloc[0] == pytest.approx(expected_xx[3])
    assert row["rhoxy_fitted(microohm_cm)"].iloc[0] == pytest.approx(expected_xy[3])
    assert row["rhoxx_residual(microohm_cm)"].iloc[0] == pytest.approx(
        group.rhoxx_uohmcm[3] - expected_xx[3])


def test_the_channel_as_the_fit_saw_it_appears_when_it_differs(tmp_path):
    """`measured` earns its column exactly where subtracting the raw one would
    mislead.

    The Hall scale of FR-007 multiplies the channel before the fit ever sees
    it, so measured minus fitted is not the raw column minus fitted, and a
    reader subtracting the wrong pair would read a residual the verdict was
    never reached on.
    """
    import types

    from mbfit import config as cfg, dataio

    source = ROOT / "tests" / "data" / "synthetic_small.csv"
    document = json.loads((ROOT / "configs" / "example_1e1h.json").read_text("utf-8"))
    document["preprocess"] = dict(document.get("preprocess", {}), rhoxy_scale=2.0)
    config = cfg.resolve(document)
    dataset = dataio.load_dataset(source, config)

    carriers = [{"name": "h1", "kind": "hole", "density_cm3": 5e20,
                 "mobility_cm2Vs": 9000.0, "conduction_share": 1.0}]
    result = types.SimpleNamespace(
        dataset=dataset, hall_polarity=1.0,
        outcomes=[types.SimpleNamespace(T_K=g.T_K, carriers=carriers)
                  for g in dataset.groups])

    path = tmp_path / runner.COMBINED
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    runner.add_model_to_combined(path, result)
    table = pd.read_csv(path)

    assert "rhoxy_measured(microohm_cm)" in table.columns
    assert "rhoxx_measured(microohm_cm)" in table.columns, "both, or the pair is odd"
    assert table["rhoxy_measured(microohm_cm)"].iloc[0] == pytest.approx(
        2.0 * table["rhoxy(microohm cm)"].iloc[0])
    assert np.allclose(
        table["rhoxy_measured(microohm_cm)"] - table["rhoxy_fitted(microohm_cm)"],
        table["rhoxy_residual(microohm_cm)"], equal_nan=True)
    # and the raw column is not the pair to subtract, which is the whole point
    assert not np.allclose(
        table["rhoxy(microohm cm)"] - table["rhoxy_fitted(microohm_cm)"],
        table["rhoxy_residual(microohm_cm)"], equal_nan=True)


def test_a_sweep_the_procedure_never_answered_keeps_its_rows(tmp_path):
    """A stop, or a count that fit nothing, leaves the model blank rather than
    dropping the measurement: the table is the reader's own data."""
    import types

    from mbfit import config as cfg, dataio

    source = ROOT / "tests" / "data" / "synthetic_small.csv"
    config = cfg.resolve(json.loads((ROOT / "configs" / "example_1e1h.json").read_text("utf-8")))
    dataset = dataio.load_dataset(source, config)
    answered = dataset.groups[0]
    result = types.SimpleNamespace(
        dataset=dataset, hall_polarity=1.0,
        outcomes=[types.SimpleNamespace(
            T_K=answered.T_K,
            carriers=[{"name": "h1", "kind": "hole", "density_cm3": 5e20,
                       "mobility_cm2Vs": 9000.0, "conduction_share": 1.0}])])

    path = tmp_path / runner.COMBINED
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    runner.add_model_to_combined(path, result)
    table = pd.read_csv(path)

    assert len(table) == sum(g.B_T.size for g in dataset.groups), "a row was dropped"
    answered_rows = table[table["T(K)"] == answered.T_K]
    silent_rows = table[table["T(K)"] != answered.T_K]
    assert answered_rows["rhoxx_fitted(microohm_cm)"].notna().all()
    assert silent_rows["rhoxx_fitted(microohm_cm)"].isna().all()


def _confirm(client, job_id, **body):
    started = client.post(f"/api/jobs/{job_id}/confirm", json=body)
    assert started.status_code == 202, started.json()
    confirmed = started.json()["job_id"]
    view = _wait(client, confirmed, timeout=600)
    assert view["state"] == "succeeded", view["error"]
    return confirmed


def test_a_confirmed_answer_downloads_the_files_the_command_line_writes(
        client, stand_in, tmp_path):
    """FR-104, FR-112. The same writers over the confirmed run's own result.

    The confirm re-runs the procedure under the settings the adjustments amount
    to rather than gathering the rows already on the page, so the files
    describe one run throughout.
    """
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)

    confirmed = _confirm(client, job_id, fixed_counts={"5-20": [2, 2]})

    from app.jobs import store
    result = store.get(confirmed).context["analysis"]
    workflow_report.write_tables(result, tmp_path)
    workflow_report.write_page(result, tmp_path, runner.REPORT_TEXT)

    page = client.get(f"/api/jobs/{confirmed}/report.html")
    assert page.status_code == 200
    assert page.content == (tmp_path / workflow_report.PAGE).read_bytes()

    archive = zipfile.ZipFile(
        io.BytesIO(client.get(f"/api/jobs/{confirmed}/tables.zip").content))
    for name in (workflow_report.SUMMARY, workflow_report.CARRIERS,
                 workflow_report.CANDIDATES):
        assert archive.read(name) == (tmp_path / name).read_bytes(), name


def test_what_produced_the_confirmed_answer_travels_with_it(client, stand_in):
    """NR-013. A reader who unzips can reach the same answer from the command
    line; without the document they would have to remember what they pressed."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    confirmed = _confirm(client, job_id, fixed_counts={"5-20": [2, 2]},
                         smooth_band=[{"range": "5-20", "strength": "normal"}])

    archive = zipfile.ZipFile(
        io.BytesIO(client.get(f"/api/jobs/{confirmed}/tables.zip").content))
    names = set(archive.namelist())
    assert runner.CONFIRMED_CONFIG in names, "the document that produced it"
    assert runner.COMBINED in names, "the data it ran on"

    document = json.loads(archive.read(runner.CONFIRMED_CONFIG))
    assert document["workflow"]["fixed_counts"] == {"5-20": [2, 2]}
    assert document["workflow"]["smooth_band"] == [
        {"range": "5-20", "strength": "normal"}]


def test_a_confirmed_answer_carries_every_temperature(client, stand_in):
    """FR-112. The confirmed answer is the whole table with the adjustments
    applied. Keeping only the adjusted sweeps would narrow the series without
    saying so."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    confirmed = _confirm(client, job_id, fixed_counts={"5": [2, 2]})
    view = client.get(f"/api/jobs/{confirmed}").json()
    assert [row["T"] for row in view["result"]["temperatures"]] == [5.0, 10.0, 20.0]


def test_the_procedures_own_answer_survives_a_confirm(client, stand_in):
    """FR-112. Confirming adds an answer; it does not erase one. A reader who
    wants to show what the procedure chose, beside what they chose, still can."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    confirmed = _confirm(client, job_id, fixed_counts={"5": [2, 2]})
    assert confirmed != job_id
    assert client.get(f"/api/jobs/{job_id}/report.html").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/tables.zip").status_code == 200


def test_a_confirm_with_nothing_adjusted_is_refused(client, stand_in):
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/confirm", json={})
    assert response.json()["code"] == "E_CONFIRM_EMPTY"


def test_an_adjustment_that_cannot_be_written_down_fails_the_request(client, stand_in):
    """A bad setting fails the request, not the job -- as a bad document does
    at the start of an analysis."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    response = client.post(f"/api/jobs/{job_id}/confirm",
                           json={"smooth_band": [{"range": "warm", "strength": "normal"}]})
    assert response.json()["code"] == "E_CONFIG_BAD_VALUE"


def test_nothing_downloads_from_an_adjustment_that_was_not_confirmed(client, stand_in):
    """FR-112 widened the download to a confirmed answer, not to every child
    job. A refit writes no files and is not a run."""
    stand_in.release.set()
    job_id = client.post("/api/analyses",
                         json={"files": _three(client), "count": "data"}).json()["job_id"]
    _wait(client, job_id)
    band, _ = _refit(client, job_id, [5.0, 10.0, 20.0])
    assert client.get(f"/api/jobs/{band}/report.html").status_code == 409
    assert client.get(f"/api/jobs/{band}/tables.zip").status_code == 409


@pytest.mark.slow
def test_one_reference_file_through_the_server_matches_the_command_line(client, tmp_path):
    """Gate 17 on one temperature: the server's tables equal the library's."""
    preview = _upload(client, ("5K.csv", (EXAMPLE / "5K.csv").read_text(encoding="utf-8")))[0]
    job_id = client.post("/api/analyses", json={"files": [_mapping(preview)], "count": "data"}).json()["job_id"]
    view = _wait(client, job_id, timeout=900)
    assert view["state"] == "succeeded", view["error"]
    verdict = view["result"]["temperatures"][0]
    # The upload fixture is generated from one carrier of each sign, so this is
    # the answer the data asks for. It read `2h+2e` while the file was a
    # measured sweep.
    assert verdict["label"] == "1h+1e" and verdict["grade"] == "B"
