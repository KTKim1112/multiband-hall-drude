"""The classical independent-carrier Drude model, in SI.

This is the physical model contract of `spec.md` section 4. Every quantity
here is SI (Article V); the boundary units are converted in `units.py`.

For one carrier of density `n`, mobility `mu` and sign `s`:

    sigma_xx = n q mu / [1 + (mu B)^2]
    sigma_xy = s n q mu^2 B / [1 + (mu B)^2]

`q` is the elementary charge, a positive number. Carriers are independent, so
conductivities add. With `sigma_xy` defined as the response of `J_x` to
`E_y`, the tensor is

    J = sigma E,    sigma = [[ sigma_xx, sigma_xy],
                            [-sigma_xy, sigma_xx]]

and the measured Hall resistivity, `E_y / J_x`, is the (2,1) element of the
inverse:

    rho_xx = +sigma_xx / (sigma_xx^2 + sigma_xy^2)
    rho_xy = +sigma_xy / (sigma_xx^2 + sigma_xy^2)

so that at positive field a single electron band gives negative `rho_xy` and
a single hole band gives positive `rho_xy` (PM-001). The sign placement in
the tensor was wrong in an earlier draft of research 2.2 and is recorded
there; it is the same error that inverted the Hall sign in the inherited
prototype.
"""

from __future__ import annotations

import numpy as np

from .constants import ELEMENTARY_CHARGE_C
from .errors import MbfitError

SIGN_ELECTRON = -1.0
SIGN_HOLE = +1.0

_KIND_TO_SIGN = {"electron": SIGN_ELECTRON, "hole": SIGN_HOLE}


def sign_of_kind(kind: str) -> float:
    """Map `electron` or `hole` to the sign used in the model.

    Raises MbfitError(E_CONFIG_BAD_CARRIER_KIND) for anything else, since an
    unrecognised kind reaches here only from a configuration document.
    """
    try:
        return _KIND_TO_SIGN[kind]
    except KeyError:
        raise MbfitError("E_CONFIG_BAD_CARRIER_KIND", kind=kind) from None


def _checked(n_per_m3, mu_m2Vs, sign):
    n = np.atleast_1d(np.asarray(n_per_m3, dtype=float))
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))
    s = np.atleast_1d(np.asarray(sign, dtype=float))
    if n.shape != mu.shape or n.shape != s.shape:
        raise ValueError(f"shape mismatch: n {n.shape}, mu {mu.shape}, sign {s.shape}")
    # NR-001. Positivity is automatic during a fit, which searches in the
    # logarithm; a violation here means a caller bypassed that, not that the
    # user supplied something wrong, so it is a programming error rather than
    # an error code. The user-facing equivalent is E_CONFIG_BOUNDS_INVALID.
    if np.any(n <= 0.0) or np.any(mu <= 0.0):
        raise ValueError("NR-001 violated: density and mobility must be positive")
    if not np.all(np.isin(s, (SIGN_ELECTRON, SIGN_HOLE))):
        raise ValueError("carrier sign must be -1 (electron) or +1 (hole)")
    return n, mu, s


def conductivity_tensor(B_T, n_per_m3, mu_m2Vs, sign):
    """Conductivity of a set of independent carriers, in S/m.

    `B_T` has shape (M,); `n_per_m3`, `mu_m2Vs` and `sign` have shape (N,).
    Returns `(sigma_xx, sigma_xy)`, each of shape (M,).
    """
    n, mu, s = _checked(n_per_m3, mu_m2Vs, sign)
    B = np.atleast_1d(np.asarray(B_T, dtype=float))

    mu_B = mu[:, None] * B[None, :]
    denominator = 1.0 + mu_B**2
    n_q = n[:, None] * ELEMENTARY_CHARGE_C

    sigma_xx = np.sum(n_q * mu[:, None] / denominator, axis=0)
    sigma_xy = np.sum(
        s[:, None] * n_q * mu[:, None] ** 2 * B[None, :] / denominator, axis=0
    )
    return sigma_xx, sigma_xy


def resistivity_from_conductivity(sigma_xx, sigma_xy, hall_polarity: float = 1.0):
    """Invert the conductivity tensor. Both arguments and results in SI.

    `hall_polarity` is PM-002: it multiplies `rho_xy`, for an experiment whose
    transverse contacts are wired opposite to the convention of PM-001. Its
    default of +1 leaves the model at PM-001.
    """
    sxx = np.asarray(sigma_xx, dtype=float)
    sxy = np.asarray(sigma_xy, dtype=float)
    determinant = sxx**2 + sxy**2
    if np.any(determinant == 0.0):
        raise MbfitError(
            "E_FIT_SINGULAR",
            where="resistivity_from_conductivity",
            n_singular=int(np.count_nonzero(determinant == 0.0)),
        )
    return sxx / determinant, hall_polarity * sxy / determinant


def conductivity_from_resistivity(rho_xx_ohm_m, rho_xy_ohm_m, hall_polarity: float = 1.0):
    """The exact inverse of `resistivity_from_conductivity`.

    The relation is its own inverse in form, because
    `rho_xx^2 + rho_xy^2 = 1 / (sigma_xx^2 + sigma_xy^2)`. The polarity of
    PM-002 is undone before inverting, so that a round trip through both
    functions is the identity for any polarity.
    """
    rxx = np.asarray(rho_xx_ohm_m, dtype=float)
    rxy = np.asarray(rho_xy_ohm_m, dtype=float) / hall_polarity
    determinant = rxx**2 + rxy**2
    if np.any(determinant == 0.0):
        raise MbfitError(
            "E_FIT_SINGULAR",
            where="conductivity_from_resistivity",
            n_singular=int(np.count_nonzero(determinant == 0.0)),
        )
    return rxx / determinant, rxy / determinant


def resistivity(B_T, n_per_m3, mu_m2Vs, sign, hall_polarity: float = 1.0):
    """Model resistivity directly from carrier parameters. SI throughout."""
    sigma_xx, sigma_xy = conductivity_tensor(B_T, n_per_m3, mu_m2Vs, sign)
    return resistivity_from_conductivity(sigma_xx, sigma_xy, hall_polarity)
