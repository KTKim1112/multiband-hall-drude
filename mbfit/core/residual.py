"""Assembling the residual vector: what is compared, and how it is weighted.

FR-018 to FR-022 and FR-049. Everything here is SI and array-shaped; the
boundary units are converted before anything reaches this module.

The order of operations matters and is fixed:

    admit records by the field window   FR-049
    convert to the comparison space     FR-019
    normalise each channel by its scale FR-020
    apply the declared channel weights  FR-021
    apply the low-field emphasis        FR-022, longitudinal only
    select the channels                 FR-018

Normalisation comes before the weights so that `weight_rhoxx = 2` means twice
as much as the Hall channel regardless of the units the two are measured in.
The scales are computed from the measurement once, not from the model, so
they do not move as the search moves.
"""

from __future__ import annotations

import numpy as np

from .drude import conductivity_from_resistivity
from .metrics import robust_scale

FIT_MODE_BOTH = "both"
FIT_MODE_LONGITUDINAL = "rhoxx"
FIT_MODE_HALL = "rhoxy"

SPACE_RESISTIVITY = "rho"
SPACE_CONDUCTIVITY = "sigma"


def admit(B_T, mask=None):
    """The records the comparison sees. FR-049.

    A mask rather than a deletion, because FR-050 requires the excluded
    records to keep being predicted and reported.
    """
    B = np.asarray(B_T, dtype=float)
    if mask is None:
        return np.ones(B.shape, dtype=bool)
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != B.shape:
        raise ValueError(f"mask shape {mask.shape} does not match field shape {B.shape}")
    return mask


def to_space(rho_xx, rho_xy, fit_space: str, hall_polarity: float = 1.0):
    """The pair of quantities the comparison is made in. FR-019."""
    if fit_space == SPACE_RESISTIVITY:
        return np.asarray(rho_xx, dtype=float), np.asarray(rho_xy, dtype=float)
    if fit_space == SPACE_CONDUCTIVITY:
        return conductivity_from_resistivity(rho_xx, rho_xy, hall_polarity)
    raise ValueError(f"fit_space must be {SPACE_RESISTIVITY!r} or {SPACE_CONDUCTIVITY!r}")


def channel_scales(rho_xx, rho_xy, fit_space: str, hall_polarity: float = 1.0):
    """The two scales of FR-020, from the measurement, computed once.

    Returned so that they can be recorded with the result: the weighting
    actually applied is then visible rather than inferred.
    """
    target_xx, target_xy = to_space(rho_xx, rho_xy, fit_space, hall_polarity)
    return robust_scale(target_xx), robust_scale(target_xy)


def low_field_weight(B_T, enabled: bool, alpha: float, B0_T: float):
    """`1 + alpha exp[-(|B|/B0)^2]`, or ones. FR-022.

    Research ledger C5: a reweighting, not a constraint, and a diagnostic
    option rather than a production setting, since it degrades the high-field
    fit by construction.
    """
    B = np.asarray(B_T, dtype=float)
    if not enabled or alpha == 0.0:
        return np.ones(B.shape, dtype=float)
    return 1.0 + float(alpha) * np.exp(-((np.abs(B) / float(B0_T)) ** 2))


def residual_vector(
    B_T,
    measured_rho_xx,
    measured_rho_xy,
    model_rho_xx,
    model_rho_xy,
    *,
    fit_mode: str = FIT_MODE_BOTH,
    fit_space: str = SPACE_RESISTIVITY,
    hall_polarity: float = 1.0,
    weight_rhoxx: float = 1.0,
    weight_rhoxy: float = 1.0,
    low_field_enabled: bool = False,
    low_field_alpha: float = 0.0,
    low_field_B0_T: float = 1.0,
    scales=None,
    mask=None,
):
    """The vector a least-squares method minimises the sum of squares of.

    Every argument is SI. `scales` is the pair from `channel_scales`; passing
    it keeps the normalisation fixed while the model moves, which is what
    makes the objective a function of the parameters alone.
    """
    admitted = admit(B_T, mask)
    B = np.asarray(B_T, dtype=float)[admitted]

    measured = to_space(
        np.asarray(measured_rho_xx, dtype=float)[admitted],
        np.asarray(measured_rho_xy, dtype=float)[admitted],
        fit_space,
        hall_polarity,
    )
    modelled = to_space(
        np.asarray(model_rho_xx, dtype=float)[admitted],
        np.asarray(model_rho_xy, dtype=float)[admitted],
        fit_space,
        hall_polarity,
    )

    if scales is None:
        scale_xx, scale_xy = robust_scale(measured[0]), robust_scale(measured[1])
    else:
        scale_xx, scale_xy = float(scales[0]), float(scales[1])

    emphasis = low_field_weight(B, low_field_enabled, low_field_alpha, low_field_B0_T)

    parts = []
    if fit_mode in (FIT_MODE_BOTH, FIT_MODE_LONGITUDINAL):
        longitudinal = (modelled[0] - measured[0]) / scale_xx
        parts.append(longitudinal * np.sqrt(float(weight_rhoxx)) * np.sqrt(emphasis))
    if fit_mode in (FIT_MODE_BOTH, FIT_MODE_HALL):
        hall = (modelled[1] - measured[1]) / scale_xy
        parts.append(hall * np.sqrt(float(weight_rhoxy)))
    if not parts:
        raise ValueError(
            f"fit_mode must be one of {FIT_MODE_BOTH!r}, "
            f"{FIT_MODE_LONGITUDINAL!r}, {FIT_MODE_HALL!r}"
        )
    return np.concatenate(parts)


def n_residuals(n_records: int, fit_mode: str) -> int:
    """How many residuals a number of admitted records produces. FR-006."""
    return n_records * (2 if fit_mode == FIT_MODE_BOTH else 1)
