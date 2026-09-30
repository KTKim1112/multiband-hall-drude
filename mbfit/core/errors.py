"""Failure signalling for the whole package.

Constitution Article IV: a function signals failure by raising an exception
carrying a stable machine-readable code, never a sentence for a human. The
Korean wording lives in the presentation layer, keyed by these codes, and can
be rewritten without touching a single test.

The registry below is the source of truth the Gate 2 test compares against
`data-model.md` section 3.
"""

from __future__ import annotations

CONFIG_CODES: tuple[str, ...] = (
    "E_CONFIG_UNREADABLE",
    "E_CONFIG_SCHEMA_VERSION",
    "E_CONFIG_UNKNOWN_FIELD",
    "E_CONFIG_MISSING_FIELD",
    "E_CONFIG_BAD_VALUE",
    "E_CONFIG_NO_CARRIERS",
    "E_CONFIG_DUPLICATE_CARRIER",
    "E_CONFIG_BAD_CARRIER_KIND",
    "E_CONFIG_BOUNDS_INVALID",
    "E_CONFIG_INIT_OUT_OF_BOUNDS",
    "E_CONFIG_UNKNOWN_CARRIER",
    "E_CONFIG_EMPTY_FIELD_WINDOW",
    "E_CONFIG_COUPLING_WITHOUT_GLOBAL",
    "E_CONFIG_BREAK_OUTSIDE_RANGE",
)

DATA_CODES: tuple[str, ...] = (
    "E_DATA_UNREADABLE",
    "E_DATA_MISSING_COLUMN",
    "E_DATA_EMPTY",
    "E_DATA_UNDERDETERMINED",
)

FIT_CODES: tuple[str, ...] = (
    "E_FIT_NO_START",
    "E_FIT_SINGULAR",
)

ERROR_CODES: tuple[str, ...] = CONFIG_CODES + DATA_CODES + FIT_CODES


class MbfitError(Exception):
    """A failure identified by a code, with machine-readable detail.

    `detail` holds whatever a caller needs to act on or a message needs to
    interpolate: the missing column names, the carrier and quantity whose
    bounds are wrong, the field at which the tensor became singular. It never
    holds a human-facing sentence.
    """

    def __init__(self, code: str, **detail: object) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code!r}")
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)

    def __repr__(self) -> str:
        return f"MbfitError({self.code!r}, {self.detail!r})"
