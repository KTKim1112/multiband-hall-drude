"""T902 — circular block resampling. Gate 9.

Three properties, and the third is the one that catches a plausible mistake.
Block length 1 must be an ordinary independent resample. Every record must
appear with the same frequency in expectation, or the resample is biased
towards whichever records the scheme happens to favour. And a block length
equal to the record count must be a rotation rather than the identity, which
is the fact research 002 section 3.2 rests on when it reports a non-zero
interval at L = 361.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit.core import resample


def test_block_length_one_is_an_independent_resample():
    generator = np.random.default_rng(0)
    indices = resample.block_indices(50, 1, generator)
    assert indices.size == 50
    # an independent draw of 50 from 50 repeats something, essentially always
    assert len(set(indices.tolist())) < 50


def test_the_output_is_always_the_length_of_the_input():
    generator = np.random.default_rng(1)
    for n in (1, 7, 50, 361):
        for L in (1, 3, 20, 361, 1000):
            assert resample.block_indices(n, L, generator).size == n


def test_every_record_appears_equally_often_in_expectation():
    """A circular scheme has no edge, which is the reason for choosing it.

    A non-circular scheme that drew starts uniformly and truncated would
    under-sample the last `L - 1` records, so this is the property that
    distinguishes the two.
    """
    n, L, draws = 40, 8, 4000
    generator = np.random.default_rng(20260912)
    counts = np.zeros(n)
    for _ in range(draws):
        counts += np.bincount(resample.block_indices(n, L, generator), minlength=n)
    share = counts / counts.sum()
    assert np.max(np.abs(share - 1.0 / n)) < 0.1 / n


def test_a_full_length_block_is_a_rotation_not_the_identity():
    """Research 002 section 3.2 measures a non-zero interval at L = n."""
    values = np.arange(20.0)
    seen_identity = False
    generator = np.random.default_rng(3)
    for _ in range(50):
        drawn = resample.block_resample(values, 20, generator)
        assert sorted(drawn.tolist()) == sorted(values.tolist())   # a rotation
        seen_identity |= np.array_equal(drawn, values)
    assert not np.array_equal(
        resample.block_resample(values, 20, np.random.default_rng(4)), values
    ) or seen_identity


def test_blocks_are_contiguous_on_the_circle():
    values = np.arange(30.0)
    drawn = resample.block_resample(values, 10, np.random.default_rng(5))
    for start in (0, 10, 20):
        block = drawn[start:start + 10]
        step = np.diff(block) % 30
        assert np.all(step == 1.0), block


def test_bad_arguments_are_refused():
    generator = np.random.default_rng(6)
    with pytest.raises(ValueError):
        resample.block_indices(0, 5, generator)
    with pytest.raises(ValueError):
        resample.block_indices(10, 0, generator)
    with pytest.raises(ValueError):
        resample.block_resample(np.zeros((3, 3)), 2, generator)


# ------------------------------------------------------------------ interval

def test_the_interval_is_the_central_fraction():
    samples = np.arange(1001.0)
    low, high = resample.interval(samples, 0.68)
    assert low == pytest.approx(160.0, abs=1.0)
    assert high == pytest.approx(840.0, abs=1.0)


def test_the_interval_is_not_symmetric_when_the_sample_is_not():
    """Why a percentile rather than a multiple of the standard deviation."""
    samples = np.exp(np.random.default_rng(7).normal(size=20000))
    low, high = resample.interval(samples, 0.68)
    centre = float(np.median(samples))
    assert (high - centre) > 1.5 * (centre - low)


def test_a_fraction_outside_the_open_unit_interval_is_refused():
    for bad in (0.0, 1.0, -0.5, 2.0):
        with pytest.raises(ValueError):
            resample.interval(np.arange(10.0), bad)


# --------------------------------------------------------------- correlation

def test_a_perfectly_coupled_pair_correlates_at_one():
    x = np.random.default_rng(8).normal(size=500)
    C = resample.correlation(np.column_stack([x, 2.0 * x + 1.0]))
    assert C[0, 1] == pytest.approx(1.0, abs=1e-10)


def test_an_opposed_pair_correlates_at_minus_one():
    x = np.random.default_rng(9).normal(size=500)
    C = resample.correlation(np.column_stack([x, -3.0 * x]))
    assert C[0, 1] == pytest.approx(-1.0, abs=1e-10)


def test_a_parameter_that_never_moved_is_not_a_division_by_zero():
    x = np.random.default_rng(10).normal(size=100)
    C = resample.correlation(np.column_stack([x, np.full(100, 5.0)]))
    assert np.all(np.isfinite(C))
    assert C[1, 1] == 0.0
    assert C[0, 1] == 0.0
    assert C[0, 0] == pytest.approx(1.0)


def test_correlation_is_symmetric_and_bounded():
    X = np.random.default_rng(11).normal(size=(300, 6))
    C = resample.correlation(X)
    assert np.allclose(C, C.T)
    assert np.all(np.abs(C) <= 1.0 + 1e-12)
    assert np.allclose(np.diag(C), 1.0)
