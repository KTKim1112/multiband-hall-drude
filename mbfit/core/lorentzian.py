"""The Lorentzian extension of the normalised conductivities, and its exact
Kramers-Kronig transform. FR-067 to FR-069.

With the conductivities normalised by their zero-field longitudinal value,

    X(B) = sigma_xx(B) / sigma_xx(0)
    Y(B) = sigma_xy(B) / sigma_xx(0)

the multiband Drude model of PM-001 makes both of these exactly sums of
Lorentzians sharing one set of mobilities:

    X(B) = sum_j  a_j / [1 + mu_j^2 B^2]
    Y(B) = sum_j  b_j B / [1 + mu_j^2 B^2]

For a carrier of density `n`, mobility `mu` and sign `s`, `a = n q mu /
sigma_xx(0)` and `b = s a mu`. So `a_j` is positive for every carrier and the
carrier sign lives entirely in the sign of `b_j`. **That is what makes the
separation of this feature possible**: `X` cannot tell an electron from a hole
and `Y` can.

The point of writing them this way is the transform. Define

    H[f](B) = (1/pi) P integral f(B') / (B - B') dB'

Then, exactly,

    H[ 1 / (1 + mu^2 B^2) ]  =  mu B / (1 + mu^2 B^2)
    H[ B / (1 + mu^2 B^2) ]  =  -(1/mu) / (1 + mu^2 B^2)

so the transform of a sum of Lorentzians is another sum of Lorentzians with
the same mobilities, and **no numerical principal-value integral is needed**.
Research 003 section 2.2 records the verification against quadrature to nine
figures, and section 2.1 records why this matters: the published method this
follows integrates numerically from -1e6 to 1e6 T, and that truncation is
simply absent here.

The requirement that `X` and `Y` share one set of `mu_j` is not cosmetic. If
they were fitted separately the two transforms would land on different
mobilities and the separation identities of `separation.py` would not close.
`fit_parameters` therefore carries one mobility vector for both channels.
"""

from __future__ import annotations

import numpy as np


def split(parameters, n_terms: int):
    """A flat parameter vector as `(a, b, mu)`.

    Laid out as `[a_1..a_n, b_1..b_n, log mu_1..log mu_n]`. The mobilities are
    carried in the logarithm for the same reason NR-002 gives for the carrier
    fit: they span decades, and a linear step is the wrong step at both ends.
    """
    p = np.asarray(parameters, dtype=float)
    n = int(n_terms)
    if p.size != 3 * n:
        raise ValueError(f"expected {3 * n} parameters for {n} terms, got {p.size}")
    return p[:n], p[n:2 * n], np.exp(p[2 * n:])


def join(a, b, mu_m2Vs) -> np.ndarray:
    """The inverse of `split`."""
    a = np.atleast_1d(np.asarray(a, dtype=float))
    b = np.atleast_1d(np.asarray(b, dtype=float))
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))
    if not (a.shape == b.shape == mu.shape):
        raise ValueError("a, b and mu must have the same shape")
    if np.any(mu <= 0.0):
        raise ValueError("mobilities must be positive")
    return np.concatenate([a, b, np.log(mu)])


def evaluate(B_T, a, b, mu_m2Vs):
    """`X(B)` and `Y(B)` from the Lorentzian parameters. SI throughout."""
    B = np.atleast_1d(np.asarray(B_T, dtype=float))[:, None]
    a = np.atleast_1d(np.asarray(a, dtype=float))[None, :]
    b = np.atleast_1d(np.asarray(b, dtype=float))[None, :]
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))[None, :]
    denominator = 1.0 + (mu * B) ** 2
    return (a / denominator).sum(axis=1), (b * B / denominator).sum(axis=1)


def transform(B_T, a, b, mu_m2Vs):
    """`X'(B)` and `Y'(B)`, the Kramers-Kronig transforms, in closed form.

    Returns the pair `(X', Y')` where

        X' = sum_j  a_j mu_j B / [1 + mu_j^2 B^2]
        Y' = sum_j  -(b_j / mu_j) / [1 + mu_j^2 B^2]

    `X'` is worth a sentence of its own. Substituting `b_j = s_j a_j mu_j`
    shows that `X'` is what `Y` would have been if every carrier were a hole.
    The measured `Y` differs from it by twice the electron part, and that
    difference is the whole of the separation.
    """
    B = np.atleast_1d(np.asarray(B_T, dtype=float))[:, None]
    a = np.atleast_1d(np.asarray(a, dtype=float))[None, :]
    b = np.atleast_1d(np.asarray(b, dtype=float))[None, :]
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))[None, :]
    denominator = 1.0 + (mu * B) ** 2
    return (a * mu * B / denominator).sum(axis=1), (-(b / mu) / denominator).sum(axis=1)


def residual(parameters, n_terms: int, B_T, X, Y, weight_X: float = 1.0, weight_Y: float = 1.0):
    """The vector a least-squares method minimises. Both channels at once.

    Both, in one vector, because the mobilities are shared. Fitting `X` first
    and `Y` afterwards would let the two channels disagree about `mu_j`, and
    the transform above is only exact when they agree.
    """
    a, b, mu = split(parameters, n_terms)
    model_X, model_Y = evaluate(B_T, a, b, mu)
    scale_X = max(float(np.max(np.abs(X))), np.finfo(float).tiny)
    scale_Y = max(float(np.max(np.abs(Y))), np.finfo(float).tiny)
    return np.concatenate([
        np.sqrt(float(weight_X)) * (model_X - np.asarray(X, dtype=float)) / scale_X,
        np.sqrt(float(weight_Y)) * (model_Y - np.asarray(Y, dtype=float)) / scale_Y,
    ])


def zero_field_value(B_T, sigma_xx, window_T: float):
    """`sigma_xx(0)`, from a low-field window rather than from one record.

    Everything downstream is divided by this number, so a single noisy record
    at `B = 0` would move the whole analysis. The longitudinal channel is even
    in field and smooth through zero, so a quadratic in `B^2` over a small
    window is both unbiased and far steadier. The window in force is recorded
    with the result, because it is a choice.
    """
    B = np.asarray(B_T, dtype=float)
    s = np.asarray(sigma_xx, dtype=float)
    if B.shape != s.shape:
        raise ValueError("field and conductivity must have the same shape")

    inside = np.abs(B) <= float(window_T)
    if np.count_nonzero(inside) < 3:
        nearest = int(np.argmin(np.abs(B)))
        return float(s[nearest]), 0
    design = np.vstack([np.ones(np.count_nonzero(inside)), B[inside] ** 2]).T
    coefficients, *_ = np.linalg.lstsq(design, s[inside], rcond=None)
    return float(coefficients[0]), int(np.count_nonzero(inside))

# ------------------------------------------- the physical parameterisation

def weights_from_ab(a, b, mu_m2Vs):
    """`(p, q)`: the hole and the electron conductivity weight of each term.

        p = (a + b/mu) / 2        q = (a - b/mu) / 2

    This is the change of variable that makes the whole feature safe, and it
    is worth seeing why. Substituting back,

        X^p = sum_j p_j / [1 + mu_j^2 B^2]
        X^n = sum_j q_j / [1 + mu_j^2 B^2]

    so **a term with `p_j >= 0` and `q_j >= 0` cannot produce a negative
    separated conductivity at any field, measured or not.** In these variables
    the extension is not an arbitrary curve fit at all: it is exactly a
    `2n`-carrier Drude model, `p_j` the hole at mobility `mu_j` and `q_j` the
    electron at the same mobility.

    Measured during design, with `p` and `q` left free: two terms at nearly
    equal mobility can take large cancelling `b_j` that are invisible in `X`
    and `Y` -- the fit residual is identical to a good solution -- and send
    `X^n` to `-77.7` where its true range is `+0.017` to `+0.498`. Worse, which
    of the two basins the search lands in depends on how many starts it was
    given, so the answer would move when a user changed an unrelated setting.
    Article VII does not survive that. Constraining `p, q >= 0` removes the bad
    basin from the problem rather than detecting it afterwards.

    Negative entries are returned rather than clipped: `spectrum.py` uses them
    to report how far an unconstrained fit strayed.
    """
    a = np.atleast_1d(np.asarray(a, dtype=float))
    b = np.atleast_1d(np.asarray(b, dtype=float))
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))
    over = b / mu
    return 0.5 * (a + over), 0.5 * (a - over)


def ab_from_weights(p, q, mu_m2Vs):
    """The inverse of `weights_from_ab`: `a = p + q`, `b = mu (p - q)`."""
    p = np.atleast_1d(np.asarray(p, dtype=float))
    q = np.atleast_1d(np.asarray(q, dtype=float))
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))
    return p + q, mu * (p - q)


def design(B_T, mu_m2Vs):
    """The matrix of the linear problem in `(p, q)` for fixed mobilities.

    Rows are `X` above `Y`; columns are the `n` hole terms then the `n`
    electron terms. With this, `[X; Y] = design @ [p; q]` and the extension
    becomes a non-negative *linear* least-squares problem once the mobilities
    are fixed -- which is what lets `spectrum.py` search over `n` mobilities
    instead of `3n` free parameters.

    Column `j` is one hole at `mu_j` and column `n+j` one electron at the same
    mobility, so this matrix is the Drude model of PM-001 and is tested
    against `drude.py` rather than asserted.
    """
    B = np.atleast_1d(np.asarray(B_T, dtype=float))[:, None]
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))[None, :]
    denominator = 1.0 + (mu * B) ** 2
    even = 1.0 / denominator
    odd = mu * B / denominator
    return np.block([[even, even], [odd, -odd]])


def split_weights(parameters, n_terms: int):
    """A flat parameter vector as `(p, q, mu)`. The constrained form.

    Laid out as `[p_1..p_n, q_1..q_n, log mu_1..log mu_n]`, so that a solver
    with box bounds enforces `p, q >= 0` directly and the problem stays smooth.
    """
    v = np.asarray(parameters, dtype=float)
    n = int(n_terms)
    if v.size != 3 * n:
        raise ValueError(f"expected {3 * n} parameters for {n} terms, got {v.size}")
    return v[:n], v[n:2 * n], np.exp(v[2 * n:])


def join_weights(p, q, mu_m2Vs) -> np.ndarray:
    """The inverse of `split_weights`."""
    p = np.atleast_1d(np.asarray(p, dtype=float))
    q = np.atleast_1d(np.asarray(q, dtype=float))
    mu = np.atleast_1d(np.asarray(mu_m2Vs, dtype=float))
    if not (p.shape == q.shape == mu.shape):
        raise ValueError("p, q and mu must have the same shape")
    if np.any(mu <= 0.0):
        raise ValueError("mobilities must be positive")
    return np.concatenate([p, q, np.log(mu)])


def residual_constrained(parameters, n_terms: int, B_T, X, Y):
    """The residual in the constrained variables. NR-011.

    Identical physics to `residual`, reached through `(p, q)` so that a bound
    of zero on each is all the constraint needs. Both channels in one vector,
    each normalised by its own scale, because the two differ by an order of
    magnitude and an unnormalised sum would fit `X` and ignore `Y`.
    """
    p, q, mu = split_weights(parameters, n_terms)
    a, b = ab_from_weights(p, q, mu)
    model_X, model_Y = evaluate(B_T, a, b, mu)
    scale_X = max(float(np.max(np.abs(X))), np.finfo(float).tiny)
    scale_Y = max(float(np.max(np.abs(Y))), np.finfo(float).tiny)
    return np.concatenate([
        (model_X - np.asarray(X, dtype=float)) / scale_X,
        (model_Y - np.asarray(Y, dtype=float)) / scale_Y,
    ])
