"""Reading the measurement, and the preprocessing that precedes any fit.

One of the two places `pandas` is allowed (`plan.md` section 2.2): a table is
read here and written in `report.py`, and between them everything is an array.

Nothing here decides anything about the physics. It maps the four declared
columns, discards what cannot be used and says how much, groups the records by
temperature, forms the even and odd parts in field if asked, and marks which
records the comparison will admit. Every count it takes is reported rather
than absorbed, because a record silently dropped is a record the reader
believes was fitted.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import ResolvedConfig
from .core import parity as parity_module
from .core.errors import MbfitError

MIRROR_EXACT = 0
MIRROR_INTERPOLATED = 1
MIRROR_ABSENT = 2


@dataclass(frozen=True)
class TemperatureGroup:
    """One field sweep. `data-model.md` section 1.3."""

    T_K: float
    B_T: np.ndarray
    rhoxx_uohmcm: np.ndarray
    rhoxy_uohmcm: np.ndarray
    in_fit_window: np.ndarray
    n_records_dropped: int
    n_mirror_interpolated: int
    n_mirror_absent: int
    # FR-065 and FR-066. Measured on the sweep as supplied, before the
    # symmetrisation of FR-008 and FR-009 removes the evidence; `None` where
    # only one field polarity was given and the question cannot be asked.
    parity_rhoxx: float | None = None
    parity_rhoxy: float | None = None
    both_polarities: bool = True

    @property
    def n_records(self) -> int:
        return int(self.B_T.size)

    @property
    def n_in_window(self) -> int:
        return int(np.count_nonzero(self.in_fit_window))

    def window(self):
        """The records the comparison admits, as `(B, rhoxx, rhoxy)`."""
        mask = self.in_fit_window
        return self.B_T[mask], self.rhoxx_uohmcm[mask], self.rhoxy_uohmcm[mask]


@dataclass(frozen=True)
class Dataset:
    groups: tuple[TemperatureGroup, ...]
    n_records_dropped: int

    @property
    def temperatures(self) -> tuple[float, ...]:
        return tuple(group.T_K for group in self.groups)


# ------------------------------------------------------------------ reading

def read_table(path: str | pathlib.Path, config: ResolvedConfig) -> pd.DataFrame:
    """Read the four declared columns. FR-001, FR-003, FR-004, FR-005."""
    try:
        table = pd.read_csv(path)
    except FileNotFoundError:
        raise MbfitError("E_DATA_UNREADABLE", path=str(path), reason="not_found") from None
    except OSError as error:
        raise MbfitError("E_DATA_UNREADABLE", path=str(path), reason=type(error).__name__) from None
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise MbfitError("E_DATA_UNREADABLE", path=str(path), reason=type(error).__name__) from None

    wanted = config.columns
    missing = [name for key, name in wanted.items() if name not in table.columns]
    if missing:
        # FR-004: every missing name, not the first one found.
        raise MbfitError(
            "E_DATA_MISSING_COLUMN",
            missing=missing,
            present=[str(c) for c in table.columns],
        )

    frame = pd.DataFrame(
        {
            "T": pd.to_numeric(table[wanted["T"]], errors="coerce"),
            "B": pd.to_numeric(table[wanted["B"]], errors="coerce"),
            "rhoxx": pd.to_numeric(table[wanted["rhoxx"]], errors="coerce"),
            "rhoxy": pd.to_numeric(table[wanted["rhoxy"]], errors="coerce"),
        }
    )
    return frame


def _drop_unusable(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """FR-005: discard what cannot be used, and count it."""
    finite = np.isfinite(frame.to_numpy(dtype=float)).all(axis=1)
    kept = frame.loc[finite].reset_index(drop=True)
    return kept, int(frame.shape[0] - kept.shape[0])


# ------------------------------------------------------------ preprocessing

def _mirror(B: np.ndarray, y: np.ndarray, tolerance: float, interpolate: bool):
    """Value of `y` at `-B`, and how it was obtained. FR-010.

    Returns `(mirror, kind)` where `kind` is one of MIRROR_EXACT,
    MIRROR_INTERPOLATED or MIRROR_ABSENT. `B` must be ascending.
    """
    target = -B
    mirror = np.empty_like(y)
    kind = np.empty(B.shape, dtype=int)

    position = np.searchsorted(B, target)
    for index, wanted in enumerate(target):
        candidates = [p for p in (position[index] - 1, position[index]) if 0 <= p < B.size]
        nearest = min(candidates, key=lambda p: abs(B[p] - wanted), default=None)
        if nearest is not None and abs(B[nearest] - wanted) <= tolerance:
            mirror[index] = y[nearest]
            kind[index] = MIRROR_EXACT
        elif interpolate and B[0] <= wanted <= B[-1]:
            mirror[index] = float(np.interp(wanted, B, y))
            kind[index] = MIRROR_INTERPOLATED
        else:
            mirror[index] = y[index]  # unused; the record is left untouched
            kind[index] = MIRROR_ABSENT
    return mirror, kind


def field_window_mask(B_T, config: ResolvedConfig) -> np.ndarray:
    """Which records the comparison admits. FR-049.

    Exposed rather than inlined so that nothing else has to reimplement the
    rule: a second copy of it would be a second place for it to be wrong.
    The window decides what is *compared*; it does not remove the records,
    which FR-050 requires to stay predicted and reported.
    """
    B = np.asarray(B_T, dtype=float)
    window = config.optimization["fit_field_range"]
    if not window["enabled"]:
        return np.ones(B.shape, dtype=bool)
    magnitude = np.abs(B)
    admitted = magnitude >= float(window["abs_min_T"])
    if window["abs_max_T"] is not None:
        admitted = admitted & (magnitude <= float(window["abs_max_T"]))
    return admitted


def _preprocess(
    T_K: float,
    B: np.ndarray,
    rhoxx: np.ndarray,
    rhoxy: np.ndarray,
    config: ResolvedConfig,
) -> TemperatureGroup:
    prep = config.preprocess

    # FR-007. Applied before anything else, since it is a correction to the
    # measurement rather than an operation on it.
    rhoxy = rhoxy * float(prep["rhoxy_scale"])

    # FR-065, and it has to be here. The symmetrisation below is what destroys
    # the wrong-parity part, so the only chance to measure how large it was is
    # before that step runs. A uniform scaling of the Hall channel does not
    # change a ratio, so taking it after FR-007 costs nothing.
    tolerance_T = float(prep["mirror_tolerance_T"])
    have_both = parity_module.both_polarities(B)
    parity_xx = parity_module.violation(B, rhoxx, parity_module.PARITY_EVEN, tolerance_T)
    parity_xy = parity_module.violation(B, rhoxy, parity_module.PARITY_ODD, tolerance_T)

    want_even = bool(prep["symmetrize_rhoxx"])
    want_odd = bool(prep["antisymmetrize_rhoxy"])
    n_interpolated = 0
    n_absent = 0

    if want_even or want_odd:
        tolerance = float(prep["mirror_tolerance_T"])
        interpolate = bool(prep["mirror_interpolate"])
        if want_even:
            mirror_xx, kind = _mirror(B, rhoxx, tolerance, interpolate)
            usable = kind != MIRROR_ABSENT
            rhoxx = np.where(usable, 0.5 * (rhoxx + mirror_xx), rhoxx)
        if want_odd:
            mirror_xy, kind = _mirror(B, rhoxy, tolerance, interpolate)
            usable = kind != MIRROR_ABSENT
            rhoxy = np.where(usable, 0.5 * (rhoxy - mirror_xy), rhoxy)
        n_interpolated = int(np.count_nonzero(kind == MIRROR_INTERPOLATED))
        n_absent = int(np.count_nonzero(kind == MIRROR_ABSENT))

    window = config.optimization["fit_field_range"]
    in_window = field_window_mask(B, config)

    if not np.any(in_window):
        raise MbfitError(
            "E_CONFIG_EMPTY_FIELD_WINDOW",
            T_K=T_K,
            abs_min_T=window["abs_min_T"],
            abs_max_T=window["abs_max_T"],
            field_span=[float(np.min(np.abs(B))), float(np.max(np.abs(B)))],
        )

    return TemperatureGroup(
        T_K=T_K,
        B_T=B,
        rhoxx_uohmcm=rhoxx,
        rhoxy_uohmcm=rhoxy,
        in_fit_window=in_window,
        n_records_dropped=0,
        n_mirror_interpolated=n_interpolated,
        n_mirror_absent=n_absent,
        parity_rhoxx=parity_xx,
        parity_rhoxy=parity_xy,
        both_polarities=have_both,
    )


# ------------------------------------------------------------------ loading

def load_dataset(path: str | pathlib.Path, config: ResolvedConfig) -> Dataset:
    """Read, clean, group and preprocess. FR-001 to FR-010, FR-049."""
    frame = read_table(path, config)
    frame, n_dropped = _drop_unusable(frame)
    if frame.empty:
        raise MbfitError("E_DATA_EMPTY", path=str(path), n_records_dropped=n_dropped)

    groups: list[TemperatureGroup] = []
    for T_K, block in frame.groupby("T", sort=True):
        block = block.sort_values("B", kind="stable")
        groups.append(
            _preprocess(
                float(T_K),
                block["B"].to_numpy(dtype=float),
                block["rhoxx"].to_numpy(dtype=float),
                block["rhoxy"].to_numpy(dtype=float),
                config,
            )
        )

    dataset = Dataset(groups=tuple(groups), n_records_dropped=n_dropped)
    check_determined(dataset, config)
    return dataset


def check_determined(dataset: Dataset, config: ResolvedConfig) -> None:
    """FR-006, as corrected: residuals against free parameters, not records.

    The residual count is the number of admitted records times the number of
    channels the comparison uses. A hundred records give two hundred residuals
    when both channels are fitted and a hundred when one is, so the same sweep
    can be determined in one mode and underdetermined in another.
    """
    free = config.n_free_parameters
    channels = config.n_channels
    for group in dataset.groups:
        residuals = group.n_in_window * channels
        if residuals < free:
            raise MbfitError(
                "E_DATA_UNDERDETERMINED",
                T_K=group.T_K,
                n_residuals=residuals,
                n_free_parameters=free,
                n_records_in_window=group.n_in_window,
                n_channels=channels,
            )


def summarise(dataset: Dataset) -> dict[str, Any]:
    """What intake did, in numbers, for the diagnostics report."""
    return {
        "n_temperatures": len(dataset.groups),
        "n_records_dropped": dataset.n_records_dropped,
        "n_mirror_interpolated": sum(g.n_mirror_interpolated for g in dataset.groups),
        "n_mirror_absent": sum(g.n_mirror_absent for g in dataset.groups),
        "n_records_excluded_by_window": sum(
            g.n_records - g.n_in_window for g in dataset.groups
        ),
    }
