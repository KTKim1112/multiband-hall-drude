"""Conversion between the units at the boundary of the program and SI.

Constitution Article V: inside the core every quantity is SI, a variable
holding a non-SI value carries the unit in its name, and conversion happens
here and nowhere else.

The unit contract is NR-004:

    density       cm^-3              at the boundary,  m^-3     inside
    mobility      cm^2 / (V s)                         m^2/(V s)
    resistivity   micro-ohm cm                         ohm m
    conductivity  S / m                                S / m
    field         T                                    T
    temperature   K                                    K

`1 micro-ohm cm = 1e-6 ohm x 1e-2 m = 1e-8 ohm m`. That factor appears twice
in every round trip and is the likeliest place for a silent error, which is
why K1 of research 2.3 tests it directly: in boundary units `1 / (n q mu)` is
a number of order 100 for a typical metal and of order 1e-8 if the factor is
dropped.
"""

from __future__ import annotations

import numpy as np

DENSITY_CM3_TO_SI = 1.0e6
MOBILITY_CM2VS_TO_SI = 1.0e-4
RESISTIVITY_UOHMCM_TO_SI = 1.0e-8


def density_to_si(n_cm3):
    """cm^-3 -> m^-3."""
    return np.asarray(n_cm3, dtype=float) * DENSITY_CM3_TO_SI


def density_from_si(n_per_m3):
    """m^-3 -> cm^-3."""
    return np.asarray(n_per_m3, dtype=float) / DENSITY_CM3_TO_SI


def mobility_to_si(mu_cm2Vs):
    """cm^2/(V s) -> m^2/(V s)."""
    return np.asarray(mu_cm2Vs, dtype=float) * MOBILITY_CM2VS_TO_SI


def mobility_from_si(mu_m2Vs):
    """m^2/(V s) -> cm^2/(V s)."""
    return np.asarray(mu_m2Vs, dtype=float) / MOBILITY_CM2VS_TO_SI


def resistivity_to_si(rho_uohmcm):
    """micro-ohm cm -> ohm m."""
    return np.asarray(rho_uohmcm, dtype=float) * RESISTIVITY_UOHMCM_TO_SI


def resistivity_from_si(rho_ohm_m):
    """ohm m -> micro-ohm cm."""
    return np.asarray(rho_ohm_m, dtype=float) / RESISTIVITY_UOHMCM_TO_SI
