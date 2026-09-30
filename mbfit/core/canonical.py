"""Canonical ordering of carriers, and detection of a change in that order.

PM-003: exchanging two carriers of the same sign leaves the model unchanged,
so the order in which they were declared carries no information. Research 4.4
measured the consequence -- 190 apparently distinct solutions of one fit were
one solution wearing different labels, and the spread among them fell from a
factor of 113 to a factor of 1 once they were ordered.

The canonical form orders carriers by **decreasing mobility within each
sign**. Mobility is chosen over density because it sets the field scale at
which a carrier becomes visible, so the ordering is stable under the
perturbations that matter. Electrons stay in the positions declared for
electrons and holes in those declared for holes; only the assignment within
each group moves.

The parameter vector is flat, `[n_0, mu_0, n_1, mu_1, ...]`, as `plan.md`
section 3 specifies.
"""

from __future__ import annotations

import numpy as np

from .drude import SIGN_ELECTRON, SIGN_HOLE


def split_parameters(params):
    """Flat `[n_0, mu_0, n_1, mu_1, ...]` into `(n, mu)`."""
    p = np.asarray(params, dtype=float)
    if p.ndim != 1 or p.size % 2 != 0:
        raise ValueError(f"parameter vector must be flat and even, got shape {p.shape}")
    return p[0::2], p[1::2]


def join_parameters(n, mu):
    """`(n, mu)` back into the flat vector."""
    n = np.asarray(n, dtype=float)
    mu = np.asarray(mu, dtype=float)
    if n.shape != mu.shape:
        raise ValueError(f"shape mismatch: n {n.shape}, mu {mu.shape}")
    out = np.empty(2 * n.size, dtype=float)
    out[0::2] = n
    out[1::2] = mu
    return out


def canonical_permutation(params, sign):
    """Indices that put carriers in canonical order.

    Returns an array `perm` such that carrier `perm[i]` belongs in position
    `i`. Positions of a given sign are filled by that sign's carriers in
    decreasing order of mobility.
    """
    _, mu = split_parameters(params)
    s = np.asarray(sign, dtype=float)
    if s.shape != mu.shape:
        raise ValueError(f"shape mismatch: sign {s.shape}, carriers {mu.shape}")

    perm = np.arange(mu.size)
    for one_sign in (SIGN_ELECTRON, SIGN_HOLE):
        positions = np.flatnonzero(s == one_sign)
        if positions.size < 2:
            continue
        # Stable sort, so an exact tie keeps the declared order rather than
        # depending on how the sort routine happens to break it.
        order = positions[np.argsort(-mu[positions], kind="stable")]
        perm[positions] = order
    return perm


def apply_permutation(params, perm):
    """Reorder a flat parameter vector by `perm`."""
    n, mu = split_parameters(params)
    perm = np.asarray(perm, dtype=int)
    return join_parameters(n[perm], mu[perm])


def canonicalise(params, sign):
    """Flat parameter vector in canonical order."""
    return apply_permutation(params, canonical_permutation(params, sign))


def order_changed(params_a, params_b, sign) -> bool:
    """Whether the canonical order differs between two parameter vectors.

    This is FR-047. A change here between adjacent temperatures is the
    commonest cause of what looks like a carrier jumping, and PM-003 makes it
    free of cost, so it must be reported alongside FR-044 rather than instead
    of it.
    """
    pa = canonical_permutation(params_a, sign)
    pb = canonical_permutation(params_b, sign)
    return bool(np.any(pa != pb))
