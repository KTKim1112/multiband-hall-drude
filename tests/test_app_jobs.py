"""What the job store is allowed to forget. FR-098, FR-112.

The store keeps the last few jobs and drops the rest, which is right: they hold
whole analyses and nothing is lost by forgetting them on restart. What it may
not drop is a job something still needs -- the analysis every adjustment hangs
from, or a job that is still running and can still be stopped.
"""

from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("fastapi")

from app import jobs                                   # noqa: E402
from app.errors import AppError                        # noqa: E402

FINAL = (jobs.SUCCEEDED, jobs.FAILED, jobs.STOPPED)


def _finished(store, job, limit_s: float = 5.0):
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        if store.get(job.job_id).state in FINAL:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job.job_id} did not finish")


def test_the_analysis_an_adjustment_hangs_from_is_not_forgotten():
    """FR-112. Every refit, coupling, precise check and confirmation names the
    analysis as its parent, and the analysis is the oldest job of the lot.

    Dropping the oldest is what the store used to do, so a reader adjusting a
    twelve-sweep answer reached the limit without trying and then confirming,
    downloading or adjusting again failed with E_JOB_NOT_FOUND -- the work all
    still there, only the thing it hung from thrown away.
    """
    store = jobs.JobStore(max_retained=2)
    analysis = _finished(store, store.submit("analysis", lambda job: {"ok": True}))

    for _ in range(6):
        _finished(store, store.submit(
            "recount", lambda job: {"ok": True},
            context={"parent": analysis.job_id}))

    assert store.get(analysis.job_id).job_id == analysis.job_id


def test_a_running_job_is_not_forgotten_while_it_can_still_be_stopped():
    """FR-098. Forgetting a running job does not stop it. The work goes on and
    the only way of asking it to stop is gone."""
    store = jobs.JobStore(max_retained=1)
    release = threading.Event()
    running = store.submit("analysis", lambda job: release.wait(10) and {"ok": True})

    for _ in range(4):
        _finished(store, store.submit("precise", lambda job: {"ok": True}))

    store.stop(running.job_id)          # raised E_JOB_NOT_FOUND before
    assert running.stopped()
    release.set()
    _finished(store, running)


def test_what_nothing_needs_is_still_forgotten():
    """The limit still does its work: finished jobs nobody points at go."""
    store = jobs.JobStore(max_retained=2)
    first = _finished(store, store.submit("precise", lambda job: {"ok": True}))
    for _ in range(4):
        _finished(store, store.submit("precise", lambda job: {"ok": True}))

    with pytest.raises(AppError) as refused:
        store.get(first.job_id)
    assert refused.value.code == "E_JOB_NOT_FOUND"
