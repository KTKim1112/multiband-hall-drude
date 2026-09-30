"""Every E_DATA_* code, and what intake promises about the records.

FR-001 to FR-010 and FR-049. The recurring theme is that nothing disappears
quietly: a record dropped, a mirror interpolated, a record outside the field
window is each counted and reported, because a record silently removed is a
record the reader believes was fitted.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio
from mbfit.core.errors import MbfitError
from tests.test_config import document

COLUMNS = {"T": "T(K)", "B": "B(T)", "rhoxx": "rxx", "rhoxy": "rxy"}


def write_csv(tmp_path, rows, header=("T(K)", "B(T)", "rxx", "rxy"), name="data.csv"):
    path = tmp_path / name
    lines = [",".join(header)]
    lines += [",".join(str(value) for value in row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def config(**changes):
    return cfg.resolve(document(columns=COLUMNS, **changes))


def sweep(T, fields, rhoxx=None, rhoxy=None):
    fields = np.asarray(fields, dtype=float)
    if rhoxx is None:
        rhoxx = 10.0 + 0.1 * fields**2
    if rhoxy is None:
        rhoxy = 0.5 * fields
    return list(zip([T] * fields.size, fields, np.asarray(rhoxx), np.asarray(rhoxy)))


def raises(code):
    return pytest.raises(MbfitError, match=code)


# ------------------------------------------------------------------ reading

def test_E_DATA_UNREADABLE_for_a_missing_file(tmp_path):
    with raises("E_DATA_UNREADABLE"):
        dataio.load_dataset(tmp_path / "absent.csv", config())


def test_E_DATA_MISSING_COLUMN_names_every_missing_one(tmp_path):
    path = write_csv(tmp_path, [(5, 1.0, 10.0)], header=("T(K)", "B(T)", "rxx"))
    with pytest.raises(MbfitError) as caught:
        dataio.load_dataset(path, config())
    assert caught.value.code == "E_DATA_MISSING_COLUMN"
    assert caught.value.detail["missing"] == ["rxy"]


def test_the_four_columns_are_found_by_their_declared_names(tmp_path):
    """FR-003: nobody names their columns the way anybody else does."""
    path = write_csv(
        tmp_path,
        sweep(5.0, [-1.0, 0.0, 1.0]),
        header=("Temperature", "Field", "Rxx", "Rxy"),
    )
    other_names = {"T": "Temperature", "B": "Field", "rhoxx": "Rxx", "rhoxy": "Rxy"}
    dataset = dataio.load_dataset(path, cfg.resolve(document(columns=other_names)))
    assert dataset.temperatures == (5.0,)


def test_E_DATA_EMPTY_when_nothing_usable_survives(tmp_path):
    path = write_csv(tmp_path, [(5, "x", "y", "z"), (5, "", "", "")])
    with raises("E_DATA_EMPTY"):
        dataio.load_dataset(path, config())


def test_FR005_unusable_records_are_dropped_and_counted(tmp_path):
    rows = sweep(5.0, np.linspace(-3.0, 3.0, 7))
    rows.append((5.0, "bad", 1.0, 1.0))
    rows.append((5.0, 2.5, "", 1.0))
    path = write_csv(tmp_path, rows)
    dataset = dataio.load_dataset(path, config())
    assert dataset.n_records_dropped == 2
    assert dataset.groups[0].n_records == 7
    assert dataio.summarise(dataset)["n_records_dropped"] == 2


# --------------------------------------------------------------- grouping

def test_FR002_records_are_grouped_by_temperature_and_sorted_in_field(tmp_path):
    rows = sweep(20.0, [1.0, -1.0, 0.0]) + sweep(5.0, [0.0, 2.0, -2.0])
    path = write_csv(tmp_path, rows)
    dataset = dataio.load_dataset(path, config())
    assert dataset.temperatures == (5.0, 20.0)
    for group in dataset.groups:
        assert np.all(np.diff(group.B_T) > 0)


def test_E_DATA_UNDERDETERMINED_counts_residuals_not_records(tmp_path):
    """FR-006 as corrected. The same sweep passes in one mode and not another.

    Four carriers are eight free parameters. Five records give ten residuals
    with both channels, which is enough, and five with one channel, which is
    not.
    """
    four_carriers = [
        {
            "name": name,
            "kind": kind,
            "density": {"init": 1e19, "min": 1e16, "max": 1e22},
            "mobility": {"init": 6000.0, "min": 1.0, "max": 50000.0},
        }
        for name, kind in (("e1", "electron"), ("e2", "electron"), ("h1", "hole"), ("h2", "hole"))
    ]
    path = write_csv(tmp_path, sweep(5.0, [-2.0, -1.0, 0.0, 1.0, 2.0]))

    both = cfg.resolve(document(columns=COLUMNS, carriers=four_carriers))
    assert both.n_free_parameters == 8 and both.n_channels == 2
    dataio.load_dataset(path, both)  # ten residuals: fine

    one = cfg.resolve(
        document(columns=COLUMNS, carriers=four_carriers, optimization={"fit_mode": "rhoxx"})
    )
    with pytest.raises(MbfitError) as caught:
        dataio.load_dataset(path, one)
    assert caught.value.code == "E_DATA_UNDERDETERMINED"
    assert caught.value.detail["n_residuals"] == 5
    assert caught.value.detail["n_free_parameters"] == 8


# ---------------------------------------------------------- preprocessing

def test_FR007_the_hall_scale_factor_is_applied(tmp_path):
    path = write_csv(tmp_path, sweep(5.0, [-1.0, 1.0]))
    plain = dataio.load_dataset(path, config()).groups[0]
    halved = dataio.load_dataset(path, config(preprocess={"rhoxy_scale": 0.5})).groups[0]
    assert np.allclose(halved.rhoxy_uohmcm, 0.5 * plain.rhoxy_uohmcm)


def test_FR008_and_FR009_take_the_even_and_odd_parts(tmp_path):
    fields = np.linspace(-3.0, 3.0, 13)
    clean_even = 10.0 + 0.1 * fields**2
    clean_odd = 0.5 * fields
    # Contaminate each channel with a little of the other symmetry, which is
    # what contact misalignment does.
    rows = sweep(5.0, fields, rhoxx=clean_even + 0.3 * fields, rhoxy=clean_odd + 0.2 * fields**2)
    path = write_csv(tmp_path, rows)

    untouched = dataio.load_dataset(path, config()).groups[0]
    assert not np.allclose(untouched.rhoxx_uohmcm, clean_even)

    cleaned = dataio.load_dataset(
        path, config(preprocess={"symmetrize_rhoxx": True, "antisymmetrize_rhoxy": True})
    ).groups[0]
    assert np.allclose(cleaned.rhoxx_uohmcm, clean_even, atol=1e-12)
    assert np.allclose(cleaned.rhoxy_uohmcm, clean_odd, atol=1e-12)


def test_FR010_a_mirror_that_must_be_interpolated_is_counted(tmp_path):
    """Fields placed so that -B is bracketed but never present."""
    fields = [-9.0, -4.5, -1.0, 2.0, 5.5, 9.0]
    path = write_csv(tmp_path, sweep(5.0, fields))
    group = dataio.load_dataset(path, config(preprocess={"symmetrize_rhoxx": True})).groups[0]
    assert group.n_mirror_interpolated > 0
    assert group.n_mirror_absent == 0


def test_FR010_a_mirror_that_is_absent_leaves_the_record_untouched(tmp_path):
    """A one-sided sweep. Nothing to average with, and the count says so."""
    fields = np.linspace(0.0, 9.0, 10)
    rows = sweep(5.0, fields, rhoxx=10.0 + 0.3 * fields)
    path = write_csv(tmp_path, rows)
    plain = dataio.load_dataset(path, config()).groups[0]
    attempted = dataio.load_dataset(
        path, config(preprocess={"symmetrize_rhoxx": True})
    ).groups[0]
    assert attempted.n_mirror_absent == 9      # every field but zero
    assert np.allclose(attempted.rhoxx_uohmcm, plain.rhoxx_uohmcm)
    assert dataio.summarise(attempted_dataset(path))["n_mirror_absent"] == 9


def attempted_dataset(path):
    return dataio.load_dataset(path, config(preprocess={"symmetrize_rhoxx": True}))


def test_FR010_interpolation_can_be_switched_off(tmp_path):
    fields = [-9.0, -4.5, -1.0, 2.0, 5.5, 9.0]
    path = write_csv(tmp_path, sweep(5.0, fields))
    without = dataio.load_dataset(
        path,
        config(preprocess={"symmetrize_rhoxx": True, "mirror_interpolate": False}),
    ).groups[0]
    assert without.n_mirror_interpolated == 0
    assert without.n_mirror_absent > 0


# ------------------------------------------------------------ field window

def test_FR049_and_FR050_the_window_excludes_from_the_comparison_only(tmp_path):
    fields = np.linspace(-9.0, 9.0, 37)
    path = write_csv(tmp_path, sweep(5.0, fields))
    group = dataio.load_dataset(
        path, config(optimization={"fit_field_range": {"enabled": True, "abs_max_T": 6.0}})
    ).groups[0]

    # Every record is still there. FR-050: the excluded region is the evidence
    # for whatever motivated excluding it.
    assert group.n_records == fields.size
    assert group.n_in_window < group.n_records
    assert np.all(np.abs(group.B_T[group.in_fit_window]) <= 6.0)
    assert np.all(np.abs(group.B_T[~group.in_fit_window]) > 6.0)

    admitted_B, admitted_xx, _ = group.window()
    assert admitted_B.size == group.n_in_window
    assert admitted_xx.size == group.n_in_window


def test_the_window_can_also_cut_the_low_field_end(tmp_path):
    fields = np.linspace(-9.0, 9.0, 37)
    path = write_csv(tmp_path, sweep(5.0, fields))
    group = dataio.load_dataset(
        path, config(optimization={"fit_field_range": {"enabled": True, "abs_min_T": 2.0}})
    ).groups[0]
    assert np.all(np.abs(group.B_T[group.in_fit_window]) >= 2.0)


def test_E_CONFIG_EMPTY_FIELD_WINDOW_when_the_window_admits_nothing(tmp_path):
    path = write_csv(tmp_path, sweep(5.0, np.linspace(-3.0, 3.0, 13)))
    with raises("E_CONFIG_EMPTY_FIELD_WINDOW"):
        dataio.load_dataset(
            path,
            config(optimization={"fit_field_range": {"enabled": True, "abs_min_T": 20.0}}),
        )
