"""Background jobs: progress, a stop, and what finished before it. FR-097, FR-098.

An analysis of twelve sweeps runs for minutes, and a precise check for minutes
per temperature. The request starts a thread, registers a job and returns; the
page polls. A thread rather than a process because the work sits in numpy and
scipy, which release the interpreter lock, and a dictionary rather than a queue
because there is one user on one machine and nothing is lost by forgetting jobs
on restart (data model 005 section 3).

The one thing added to the sibling project's job store is the stop. It is a
flag the work asks about before every fit; it does not kill a thread, which
Python cannot do safely, so the delay is bounded by one fit budget (AC-033).
"""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from mbfit.core.errors import MbfitError

from .errors import AppError

MAX_RETAINED = 32

PENDING, RUNNING, SUCCEEDED, FAILED, STOPPED = (
    "pending", "running", "succeeded", "failed", "stopped")


class Stop(Exception):
    """Raised by work that noticed the stop flag. `partial` is kept, if any."""

    def __init__(self, partial: Any = None) -> None:
        super().__init__("stopped")
        self.partial = partial


@dataclass
class Job:
    job_id: str
    kind: str
    state: str = PENDING
    progress: dict = field(default_factory=dict)
    result: Any = None
    error: dict | None = None
    # Anything the work wants to leave for a later request -- the analysis
    # object a precise check starts from, the directory the tables were
    # written to. Never serialised.
    context: dict = field(default_factory=dict)
    stop_requested: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def report(self, event: dict) -> None:
        with self.lock:
            self.progress = dict(event)

    def stopped(self) -> bool:
        return self.stop_requested.is_set()

    def view(self) -> dict:
        """A consistent copy for a poll, never observed half-written."""
        with self.lock:
            return {
                "job_id": self.job_id,
                "kind": self.kind,
                "state": self.state,
                "progress": dict(self.progress),
                "error": self.error,
                "result": self.result,
                "preliminary": self.context.get("preliminary"),
            }


class JobStore:
    """In-process registry, safe across threads."""

    def __init__(self, max_retained: int = MAX_RETAINED) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max = max_retained

    def _forget_what_nothing_needs(self) -> None:
        """Drop finished, unreferenced jobs when over the limit. FR-098, FR-112.

        The limit used to take whichever job was oldest. The oldest is the
        analysis: every refit, coupling, precise check and confirmation is
        started from it and keeps its id as `parent`. A reader adjusting a
        twelve-sweep answer reaches the limit without trying, and then
        confirming, downloading or adjusting again failed with
        E_JOB_NOT_FOUND -- the work was all still there, only the thing it
        hung from had been thrown away. A running job could be dropped too,
        and then it went on computing with no way left to stop it (FR-098).

        Called with the lock held.
        """
        while len(self._order) > self._max:
            needed = {job.context.get("parent") for job in self._jobs.values()}
            for position, job_id in enumerate(self._order):
                job = self._jobs.get(job_id)
                if job is None:                     # already gone; tidy the order
                    self._order.pop(position)
                    break
                if job.state in (PENDING, RUNNING) or job_id in needed:
                    continue
                self._jobs.pop(job_id, None)
                self._order.pop(position)
                break
            else:
                # Everything retained is running or still referenced. Holding
                # more than the limit is the lesser fault: the alternative is
                # answering a request about work the reader can see running.
                return

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise AppError("E_JOB_NOT_FOUND", job_id=job_id)
        return job

    def stop(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.stop_requested.set()
        return job

    def submit(self, kind: str, work: Callable[[Job], Any],
               context: dict | None = None) -> Job:
        job = Job(job_id=uuid.uuid4().hex, kind=kind, context=dict(context or {}))
        with self._lock:
            self._jobs[job.job_id] = job
            self._order.append(job.job_id)
            self._forget_what_nothing_needs()

        def run() -> None:
            with job.lock:
                job.state = RUNNING
            try:
                result = work(job)
            except Stop as stop:
                with job.lock:
                    job.result = stop.partial
                    job.state = STOPPED
                return
            except (AppError, MbfitError) as exc:
                payload = (exc.payload() if isinstance(exc, AppError)
                           else {"code": exc.code, "params": _plain(exc.detail)})
                with job.lock:
                    job.error = payload
                    job.state = FAILED
                return
            except Exception as exc:                          # noqa: BLE001
                # Still a code: a job that never finishes is worse than one
                # that says it could not (Article IV).
                with job.lock:
                    job.error = {"code": "E_INTERNAL",
                                 "params": {"detail": f"{type(exc).__name__}: {exc}",
                                            "trace": traceback.format_exc(limit=5)}}
                    job.state = FAILED
                return
            with job.lock:
                job.result = result
                job.state = SUCCEEDED

        threading.Thread(target=run, name=f"{kind}-{job.job_id[:8]}", daemon=True).start()
        return job


def _plain(value):
    from .errors import _plain as plain
    return plain(value)


store = JobStore()
