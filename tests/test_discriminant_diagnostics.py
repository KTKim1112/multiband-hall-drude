"""T805 — the three Phase 8 codes, raised from data rather than asserted. Gate 8.

`D_HARMONIC_LADDER`, `D_PARITY_VIOLATION` and `D_SINGLE_POLARITY` each have to
be provoked by a sweep that really carries the condition, and each has to stay
quiet on the reference sweeps that do not. A diagnostic that fires on
everything is as useless as one that fires on nothing.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting
from mbfit.core.drude import SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "configs" / "synthetic_5K.json"
FIELDS = np.round(np.arange(-9.0, 9.0001, 0.05), 4)


def _write(path, B, rhoxx, rhoxy, T_K=5.0):
    """A sweep on disk, written at full precision.

    `repr` of a numpy scalar is `np.float64(...)` from numpy 2 onwards, which
    is not a number any reader will accept, so every value goes through
    `float` first.
    """
    lines = ["T(K),B(T),rhoxx(microohm cm),rhoxy(microohm cm)"]
    for b, xx, xy in zip(B, rhoxx, rhoxy):
        lines.append(f"{T_K!r},{float(b)!r},{float(xx)!r},{float(xy)!r}")
    path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return path


def _document(carriers, **sections):
    doc = {
        "schema_version": "1.0",
        "columns": {"T": "T(K)", "B": "B(T)",
                    "rhoxx": "rhoxx(microohm cm)", "rhoxy": "rhoxy(microohm cm)"},
        "carriers": carriers,
        "optimization": {"multi_start": 4},
    }
    doc.update(sections)
    return doc


def _carrier(name, kind, n, mu):
    return {
        "name": name, "kind": kind,
        "density": {"init": n, "min": 1e15, "max": 1e24},
        "mobility": {"init": mu, "min": 1.0, "max": 1e6},
    }


def _run(path, document):
    config = cfg.resolve(document)
    dataset = dataio.load_dataset(path, config)
    result = fitting.fit_dataset(dataset, config)
    return result, dataset, diagnostics.collect(result, dataset)


# -------------------------------------------------------- D_HARMONIC_LADDER

def test_a_single_orbit_read_as_three_carriers_raises_the_ladder(tmp_path):
    """Research 002 section 4: harmonics of one orbit look like several bands.

    Built as the expansion predicts -- mobilities mu, mu/2, mu/3, weights
    falling, all one sign -- and then fitted as three independent hole
    carriers, which is what a user with no discriminant would do.
    """
    mu0 = 12000.0
    mus = [mu0, mu0 / 2.0, mu0 / 3.0]
    ns = [6.0e20, 2.0e20, 6.0e19]
    xx, xy = resistivity(
        FIELDS, density_to_si(ns), mobility_to_si(mus), [SIGN_HOLE] * 3)
    path = _write(tmp_path / "ladder.csv",
                  FIELDS, resistivity_from_si(xx), resistivity_from_si(xy))

    document = _document([
        _carrier("a", "hole", 6.0e20, mu0),
        _carrier("b", "hole", 2.0e20, mu0 / 2.0),
        _carrier("c", "hole", 6.0e19, mu0 / 3.0),
    ])
    _, _, found = _run(path, document)

    codes = [entry.code for entry in found]
    assert "D_HARMONIC_LADDER" in codes


def test_the_reference_sweeps_do_not_raise_the_ladder():
    """Research 002 section 4.1. The discriminant has to discriminate."""
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_series.csv", config)
    result = fitting.fit_dataset(dataset, config)
    found = diagnostics.collect(result, dataset)
    assert not any(entry.code == "D_HARMONIC_LADDER" for entry in found)


# ------------------------------------------------------- D_PARITY_VIOLATION

def test_a_contact_admixture_raises_the_parity_violation(tmp_path):
    """The defect FR-065 exists to catch, end to end through intake."""
    reference = ROOT / "tests" / "data" / "synthetic_5K.csv"
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    clean = dataio.load_dataset(reference, config).groups[0]

    path = _write(
        tmp_path / "contaminated.csv",
        clean.B_T,
        clean.rhoxx_uohmcm,
        clean.rhoxy_uohmcm + 0.05 * clean.rhoxx_uohmcm,
    )
    _, _, found = _run(path, json.loads(REFERENCE.read_text(encoding="utf-8")))

    violations = [e for e in found if e.code == "D_PARITY_VIOLATION"]
    assert len(violations) == 1
    assert violations[0].where["channel"] == "rhoxy"
    assert violations[0].measured > violations[0].threshold


def test_the_reference_sweep_raises_no_parity_violation():
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    found = diagnostics.collect(result, dataset)
    assert not any(e.code == "D_PARITY_VIOLATION" for e in found)


def test_symmetrising_does_not_hide_the_violation(tmp_path):
    """The measurement is taken before FR-008 and FR-009 run, so it survives.

    This is the test that would fail if the parity were ever measured after
    symmetrisation: the sweep below is symmetrised by the program itself, and
    the diagnostic must still report what arrived.
    """
    reference = ROOT / "tests" / "data" / "synthetic_5K.csv"
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    clean = dataio.load_dataset(reference, config).groups[0]
    path = _write(
        tmp_path / "contaminated.csv",
        clean.B_T,
        clean.rhoxx_uohmcm,
        clean.rhoxy_uohmcm + 0.05 * clean.rhoxx_uohmcm,
    )

    document = json.loads(REFERENCE.read_text(encoding="utf-8"))
    document["preprocess"] = {"symmetrize_rhoxx": True, "antisymmetrize_rhoxy": True}
    _, dataset, found = _run(path, document)

    # the data the fit saw is clean ...
    group = dataset.groups[0]
    assert np.max(np.abs(group.rhoxy_uohmcm + group.rhoxy_uohmcm[::-1])) < 1e-9
    # ... and the diagnostic still says what had to be removed
    assert any(e.code == "D_PARITY_VIOLATION" for e in found)


# -------------------------------------------------------- D_SINGLE_POLARITY

def test_one_polarity_only_is_reported(tmp_path):
    """FR-066: unmeasurable is not the same as zero."""
    reference = ROOT / "tests" / "data" / "synthetic_5K.csv"
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    clean = dataio.load_dataset(reference, config).groups[0]
    half = clean.B_T > 0

    path = _write(tmp_path / "half.csv", clean.B_T[half],
                  clean.rhoxx_uohmcm[half], clean.rhoxy_uohmcm[half])
    _, dataset, found = _run(path, json.loads(REFERENCE.read_text(encoding="utf-8")))

    assert dataset.groups[0].parity_rhoxy is None
    assert any(e.code == "D_SINGLE_POLARITY" for e in found)
    # and it does not also claim a violation it could not measure
    assert not any(e.code == "D_PARITY_VIOLATION" for e in found)


def test_a_two_sided_sweep_does_not_claim_single_polarity():
    config = cfg.resolve(json.loads(REFERENCE.read_text(encoding="utf-8")))
    dataset = dataio.load_dataset(ROOT / "tests" / "data" / "synthetic_5K.csv", config)
    result = fitting.fit_dataset(dataset, config)
    found = diagnostics.collect(result, dataset)
    assert not any(e.code == "D_SINGLE_POLARITY" for e in found)
