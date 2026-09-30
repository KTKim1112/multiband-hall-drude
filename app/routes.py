"""The endpoints of data model 005 section 1.

Validation of shape is Pydantic's; validation of meaning -- a column the file
lacks, a temperature two files claim -- is `tables.py`'s, and both leave as
codes (FR-105).
"""

from __future__ import annotations

import io
import pathlib
import tempfile
import threading
import zipfile

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from mbfit import workflow, workflow_report
# AC-036 and FR-090 are one bound, declared once in the library so the command
# line and the page cannot drift apart about what a reader may pin.
from mbfit.config import MAX_PINNED_CARRIERS

from . import runner, tables
from .errors import AppError
from .jobs import SUCCEEDED, store

router = APIRouter(prefix="/api")

_uploads: dict[str, tables.Table] = {}
_uploads_order: list[str] = []
_uploads_lock = threading.Lock()
MAX_UPLOADS = 256

#: One directory for the process. Every job writes under it and nothing is
#: written anywhere else (data model 005 section 3).
_WORKROOT = pathlib.Path(tempfile.mkdtemp(prefix="mbfit-app-"))


class MappingIn(BaseModel):
    file_id: str
    B: str | None = None
    rhoxx: str | None = None
    rhoxy: str | None = None
    T_column: str | None = None
    T_K: float | None = None
    field_unit: str = "T"
    resistivity_unit: str = "uOhm_cm"


class AnalysisIn(BaseModel):
    files: list[MappingIn]
    # FR-099. The rule for the carrier count. "data" unless the reader holds
    # the count to the spectrum's peaks, which needs evidence beyond transport.
    count: str = "data"
    symmetrize_rhoxx: bool = False
    antisymmetrize_rhoxy: bool = False
    document: dict | None = None


class PreciseIn(BaseModel):
    T_K: float


class RecountIn(BaseModel):
    temperatures: list[float]
    holes: int
    electrons: int


class SmoothIn(BaseModel):
    # one of workflow.SMOOTHING_STRENGTHS
    strength: str


class ConfirmIn(BaseModel):
    # FR-112. Settings, not the numbers already on the page: the procedure is
    # run again under them, which is what makes the tables the command line's.
    fixed_counts: dict[str, list[int]] = {}
    smooth_band: list[dict] = []


@router.post("/files")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    """FR-093, FR-094. Read every file and propose a mapping for each."""
    previews = []
    for item in files:
        raw = await item.read()
        table = tables.parse(item.filename or "upload", raw)
        with _uploads_lock:
            _uploads[table.file_id] = table
            _uploads_order.append(table.file_id)
            while len(_uploads_order) > MAX_UPLOADS:
                _uploads.pop(_uploads_order.pop(0), None)
        previews.append(table.preview())
    if not previews:
        raise AppError("E_UPLOAD_EMPTY")
    return {"files": previews}


@router.post("/analyses", status_code=202)
def start_analysis(body: AnalysisIn) -> dict:
    """FR-097, FR-099, FR-100, FR-102."""
    if body.count not in workflow.MODES:
        raise AppError("E_COUNT_RULE_UNKNOWN", count=body.count)
    with _uploads_lock:
        held = dict(_uploads)
    mappings = [tables.Mapping(**item.model_dump()) for item in body.files]
    combined = tables.combine(held, mappings)
    document, preliminary = runner.document_for(
        body.document, body.count, body.symmetrize_rhoxx, body.antisymmetrize_rhoxy)

    job = store.submit(
        "analysis",
        lambda job: runner.analysis(combined, document, body.count,
                                    _WORKROOT / job.job_id)(job),
        context={"preliminary": preliminary, "supplied": body.document is not None},
    )
    return {"job_id": job.job_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return store.get(job_id).view()


@router.post("/jobs/{job_id}/stop", status_code=202)
def stop_job(job_id: str) -> dict:
    """FR-098."""
    return {"job_id": store.stop(job_id).job_id}


@router.post("/jobs/{job_id}/precise", status_code=202)
def start_precise(job_id: str, body: PreciseIn) -> dict:
    """FR-101. A new job, started from a finished analysis."""
    parent = store.get(job_id)
    if parent.kind != "analysis" or parent.state != SUCCEEDED:
        raise AppError("E_JOB_NOT_FINISHED", job_id=job_id)
    runner.outcome_for_precise(parent, body.T_K)            # refuse before starting
    work = runner.precise(parent, body.T_K)
    job = store.submit("precise", work, context={"parent": job_id})
    return {"job_id": job.job_id}


@router.post("/jobs/{job_id}/recount", status_code=202)
def start_recount(job_id: str, body: RecountIn) -> dict:
    """FR-109. A new job, started from a finished analysis."""
    parent = store.get(job_id)
    if parent.kind != "analysis" or parent.state != SUCCEEDED:
        raise AppError("E_JOB_NOT_FINISHED", job_id=job_id)
    total = body.holes + body.electrons
    if (body.holes < 0 or body.electrons < 0 or not body.temperatures
            or not 1 <= total <= MAX_PINNED_CARRIERS):
        raise AppError("E_RECOUNT_INVALID", holes=body.holes,
                       electrons=body.electrons, most=MAX_PINNED_CARRIERS,
                       temperatures=list(body.temperatures))
    for T_K in body.temperatures:
        runner.outcome_for_recount(parent, T_K)             # refuse before starting
    work = runner.recount(parent, body.temperatures, body.holes, body.electrons)
    job = store.submit("recount", work, context={"parent": job_id})
    return {"job_id": job.job_id}


@router.post("/jobs/{job_id}/smooth", status_code=202)
def start_smooth(job_id: str, body: SmoothIn) -> dict:
    """FR-109. The coupling, asked of a refit that has already answered.

    It was once the tail of the refit's own job. A coupling over a long band
    takes far longer than the refits it follows, so asking for one withheld the
    refit that was already complete. Separated, a refit answers on its own and
    a stopped coupling leaves it standing.
    """
    parent = store.get(job_id)
    if body.strength not in workflow.SMOOTHING_STRENGTHS:
        raise AppError("E_SMOOTHING_UNKNOWN", smooth=body.strength,
                       known=list(workflow.SMOOTHING_STRENGTHS))
    work = runner.smooth(parent, body.strength)             # refuses before starting
    job = store.submit("smooth", work, context={"parent": job_id})
    return {"job_id": job.job_id}


@router.post("/jobs/{job_id}/confirm", status_code=202)
def start_confirm(job_id: str, body: ConfirmIn) -> dict:
    """FR-112. The adjustments, confirmed by running the procedure under them.

    Not instant: it is an analysis, and pinning a count does not skip the
    search. What it buys is that the files downloaded afterwards are the files
    the command line writes for the document downloaded with them (NR-013).
    """
    parent = store.get(job_id)
    document = runner.document_for_confirm(parent, body.fixed_counts,
                                           body.smooth_band)
    job = store.submit(
        "confirm",
        lambda new: runner.confirm(parent, document, _WORKROOT / new.job_id)(new),
        context={"parent": job_id})
    return {"job_id": job.job_id}


def _finished_dir(job_id: str) -> pathlib.Path:
    job = store.get(job_id)
    # FR-112. A confirmed answer is downloadable too, and lives in its own
    # directory so that the procedure's own answer stays downloadable beside
    # it. A refit or a coupling still cannot pass: they write no files.
    if (job.kind not in ("analysis", "confirm") or job.state != SUCCEEDED
            or "workdir" not in job.context):
        raise AppError("E_JOB_NOT_FINISHED", job_id=job_id)
    return job.context["workdir"]


@router.get("/jobs/{job_id}/report.html")
def download_page(job_id: str) -> FileResponse:
    """FR-104. The page the command line writes."""
    page = _finished_dir(job_id) / workflow_report.PAGE
    return FileResponse(page, media_type="text/html; charset=utf-8",
                        filename=workflow_report.PAGE)


@router.get("/jobs/{job_id}/tables.zip")
def download_tables(job_id: str) -> Response:
    """FR-104. The three tables the command line writes."""
    folder = _finished_dir(job_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in (workflow_report.SUMMARY, workflow_report.CARRIERS,
                     workflow_report.CANDIDATES):
            archive.write(folder / name, arcname=name)
        # FR-104, NR-013. What produced them travels with them, so that a
        # reader can reach the same answer from the command line rather than
        # having to remember what they pressed.
        for name in (runner.CONFIRMED_CONFIG, runner.COMBINED):
            if (folder / name).exists():
                archive.write(folder / name, arcname=name)
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="tables.zip"'})
