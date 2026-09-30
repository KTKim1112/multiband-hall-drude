"""Failures the server signals, as codes. Data model 005 section 2.

Article IV applies here as in the library: a code and machine-readable
parameters, never a sentence. The page turns a code into Korean, and
`mbfit.messages` does the same for the command line; neither is consulted here.
"""

from __future__ import annotations

APP_CODES: tuple[str, ...] = (
    "E_UPLOAD_EMPTY",
    "E_UPLOAD_UNREADABLE",
    "E_UPLOAD_NO_TABLE",
    "E_UPLOAD_SPREADSHEET",
    "E_FILE_UNKNOWN",
    "E_MAPPING_INCOMPLETE",
    "E_MAPPING_UNKNOWN_COLUMN",
    "E_MAPPING_BAD_UNIT",
    "E_TEMPERATURE_DUPLICATE",
    "E_COUNT_RULE_UNKNOWN",
    "E_JOB_NOT_FOUND",
    "E_JOB_NOT_FINISHED",
    "E_PRECISE_NO_ANSWER",
    "E_PRECISE_UNKNOWN_TEMPERATURE",
    "E_RECOUNT_INVALID",
    "E_SMOOTHING_TOO_FEW",
    "E_SMOOTHING_UNKNOWN",
    "E_SMOOTH_NO_BAND",
    "E_BAND_COUNTS_DIFFER",
    "E_BUDGET_EXPIRED",
    "E_CONFIRM_EMPTY",
    "E_REQUEST_INVALID",
    "E_INTERNAL",
)

#: HTTP status per code. Anything unlisted is 422: the request was well formed
#: but the data or settings in it cannot produce a result, which is not a
#: server fault.
STATUS: dict[str, int] = {
    "E_FILE_UNKNOWN": 404,
    "E_JOB_NOT_FOUND": 404,
    "E_JOB_NOT_FINISHED": 409,
    "E_SMOOTH_NO_BAND": 409,
    "E_INTERNAL": 500,
}


class AppError(Exception):
    """A failure identified by a code, with parameters for the message."""

    def __init__(self, code: str, **params: object) -> None:
        if code not in APP_CODES:
            raise ValueError(f"unknown application code: {code!r}")
        super().__init__(code)
        self.code = code
        self.params = dict(params)

    def payload(self) -> dict:
        return {"code": self.code, "params": _plain(self.params)}


def _plain(value):
    """Parameters as JSON values: tuples become lists, numbers stay numbers."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
