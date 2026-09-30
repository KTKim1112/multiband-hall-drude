"""End to end, and the reproduction Gate 6 asks for.

A run on the example data must write every file `data-model.md` section 4
lists, and re-running from the emitted `resolved_config.json` must reproduce
every number. A run made with `--no-priors` must reproduce from its own
emitted configuration **without** the switch, which is the test that FR-037
records what was in force rather than what was declared.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from mbfit import config as cfg
from mbfit.cli import main

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: One carrier of each sign over a narrow field range. These tests exercise
#: the command line's plumbing, not the physics, so the quick fixture serves;
#: `tests/data/make_synthetic.py` writes it and nothing here is measured.
EXAMPLE = ROOT / "tests" / "data" / "synthetic_small.csv"

BASE_CONFIG = {
    "schema_version": "1.0",
    "columns": {
        "T": "T(K)",
        "B": "B(T)",
        "rhoxx": "rhoxx(microohm cm)",
        "rhoxy": "rhoxy(microohm cm)",
    },
    "carriers": [
        {
            "name": "e1",
            "kind": "electron",
            "density": {"init": 1e19, "min": 1e16, "max": 1e22},
            "mobility": {"init": 6000.0, "min": 1.0, "max": 50000.0},
        },
        {
            "name": "h1",
            "kind": "hole",
            "density": {"init": 1e19, "min": 1e16, "max": 1e22},
            "mobility": {"init": 6000.0, "min": 1.0, "max": 50000.0},
        },
    ],
    "optimization": {"multi_start": 3},
    "output": {"make_plots": False},
}


def write_config(tmp_path, **changes):
    document = json.loads(json.dumps(BASE_CONFIG))
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(document.get(key), dict):
            document[key].update(value)
        else:
            document[key] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def csv_contents(directory: pathlib.Path, skip=()):
    return {
        path.name: path.read_bytes()
        for path in sorted(directory.glob("*.csv"))
        if path.name not in skip
    }


# ================================================================= Gate 6

def test_a_run_writes_every_file_the_data_model_lists(tmp_path):
    out = tmp_path / "results"
    config = write_config(tmp_path, output={"make_plots": True, "plot_dpi": 60})
    assert main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)]) == 0

    present = {path.name for path in out.iterdir()}
    assert "resolved_config.json" in present
    assert "fit_parameters_vs_T.csv" in present
    assert "fit_metrics_vs_T.csv" in present
    assert "diagnostics.csv" in present
    assert "parameters_vs_T.png" in present
    for temperature in ("5K", "10K", "20K"):
        assert f"{temperature}_fit.csv" in present
        assert f"multistart_{temperature}.csv" in present
        assert f"{temperature}_rhoxx.png" in present
        assert f"{temperature}_rhoxy.png" in present


def test_the_emitted_configuration_reproduces_the_run_exactly(tmp_path):
    """FR-037 and NR-005, asserted on the bytes."""
    first, second = tmp_path / "first", tmp_path / "second"
    config = write_config(tmp_path)
    assert main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(first)]) == 0

    emitted = first / "resolved_config.json"
    assert main(["--data", str(EXAMPLE), "--config", str(emitted), "--out", str(second)]) == 0

    assert csv_contents(first) == csv_contents(second)


def test_a_no_priors_run_reproduces_without_the_switch(tmp_path):
    """The record says what was in force, not what was declared. FR-057."""
    stripped, again = tmp_path / "stripped", tmp_path / "again"
    config = write_config(
        tmp_path,
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2,
                      "loss": "soft_l1"},
        smoothing={"enabled": True, "order": 2, "lambda_density": 1.0},
    )
    assert main(["--data", str(EXAMPLE), "--config", str(config),
                 "--out", str(stripped), "--no-priors"]) == 0

    emitted = json.loads((stripped / "resolved_config.json").read_text(encoding="utf-8"))
    assert emitted["smoothing"]["enabled"] is False
    assert emitted["optimization"]["loss"] == "linear"
    assert emitted["smoothing"]["lambda_density"] == 1.0   # declared strength survives

    assert main(["--data", str(EXAMPLE), "--config", str(stripped / "resolved_config.json"),
                 "--out", str(again)]) == 0

    # Every number is identical. The diagnostics differ by exactly one row,
    # and correctly so: the first run had a switch to report and the second
    # had none, since the configuration it was handed already carried the
    # values that were in force.
    assert csv_contents(stripped, skip={"diagnostics.csv"}) == csv_contents(
        again, skip={"diagnostics.csv"}
    )
    first_rows = (stripped / "diagnostics.csv").read_text(encoding="utf-8").splitlines()
    second_rows = (again / "diagnostics.csv").read_text(encoding="utf-8").splitlines()
    assert [r for r in first_rows if "D_PRIORS_DISABLED" not in r] == second_rows
    assert any("D_PRIORS_DISABLED" in r for r in first_rows)


def test_the_switch_changes_the_answer_and_says_so(tmp_path):
    """If it changed nothing, the Article X check would be worthless."""
    declared, stripped = tmp_path / "declared", tmp_path / "stripped"
    config = write_config(
        tmp_path,
        optimization={"temperature_strategy": "global_smooth", "multi_start": 2},
        smoothing={"enabled": True, "order": 1, "lambda_density": 500.0},
    )
    assert main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(declared)]) == 0
    assert main(["--data", str(EXAMPLE), "--config", str(config),
                 "--out", str(stripped), "--no-priors"]) == 0

    with_prior = (declared / "fit_parameters_vs_T.csv").read_text(encoding="utf-8")
    without = (stripped / "fit_parameters_vs_T.csv").read_text(encoding="utf-8")
    assert with_prior != without

    diagnostics_declared = (declared / "diagnostics.csv").read_text(encoding="utf-8")
    diagnostics_stripped = (stripped / "diagnostics.csv").read_text(encoding="utf-8")
    assert "D_PRIORS_ACTIVE" in diagnostics_declared
    assert "D_PRIORS_DISABLED" in diagnostics_stripped
    assert "D_PRIORS_ACTIVE" not in diagnostics_stripped


# ================================================================= contents

def test_the_per_temperature_table_covers_every_record_in_both_spaces(tmp_path):
    import pandas as pd

    out = tmp_path / "results"
    config = write_config(tmp_path)
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    frame = pd.read_csv(out / "5K_fit.csv")

    assert len(frame) == 49
    for column in (
        "B(T)", "in_fit_window",
        "rhoxx_measured(microohm_cm)", "rhoxx_fitted(microohm_cm)", "rhoxx_residual(microohm_cm)",
        "rhoxy_measured(microohm_cm)", "rhoxy_fitted(microohm_cm)", "rhoxy_residual(microohm_cm)",
        "sigmaxx_measured(S_per_m)", "sigmaxx_fitted(S_per_m)",
        "sigmaxy_measured(S_per_m)", "sigmaxy_fitted(S_per_m)",
    ):
        assert column in frame.columns


def test_the_parameter_table_carries_both_orders(tmp_path):
    import pandas as pd

    out = tmp_path / "results"
    config = write_config(tmp_path)
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    frame = pd.read_csv(out / "fit_parameters_vs_T.csv")

    assert "e1_density(cm^-3)" in frame.columns
    assert any(name.startswith("canonical1_") for name in frame.columns)


def test_the_metric_table_reports_the_conditioning_beside_the_fit_quality(tmp_path):
    import pandas as pd

    out = tmp_path / "results"
    config = write_config(tmp_path)
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    frame = pd.read_csv(out / "fit_metrics_vs_T.csv")

    for column in ("R2_rhoxx", "R2_rhoxy", "condition_number",
                   "smallest_singular_value", "channel_scale_rhoxx", "seed"):
        assert column in frame.columns
    assert (frame["condition_number"] > 0).all()


def test_every_start_is_written_out_not_only_the_best(tmp_path):
    import pandas as pd

    out = tmp_path / "results"
    config = write_config(tmp_path, optimization={"multi_start": 4})
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    frame = pd.read_csv(out / "multistart_5K.csv")
    assert len(frame) == 4
    assert list(frame["start_index"]) == [0, 1, 2, 3]


def test_the_diagnostics_file_names_its_thresholds(tmp_path):
    import pandas as pd

    out = tmp_path / "results"
    config = write_config(tmp_path)
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    frame = pd.read_csv(out / "diagnostics.csv")

    assert list(frame.columns) == [
        "code", "severity", "where", "measured", "threshold", "threshold_source"
    ]
    assert len(frame) > 0
    assert frame["threshold_source"].notna().all()


def test_plots_can_be_switched_off_without_affecting_anything_else(tmp_path):
    with_plots, without = tmp_path / "with", tmp_path / "without"
    main(["--data", str(EXAMPLE),
          "--config", str(write_config(tmp_path, output={"make_plots": True, "plot_dpi": 60})),
          "--out", str(with_plots)])
    main(["--data", str(EXAMPLE),
          "--config", str(write_config(tmp_path, output={"make_plots": False})),
          "--out", str(without)])

    assert any(path.suffix == ".png" for path in with_plots.iterdir())
    assert not any(path.suffix == ".png" for path in without.iterdir())
    assert csv_contents(with_plots) == csv_contents(without)


# =================================================================== failure

@pytest.mark.parametrize(
    "argv_change,expected",
    [
        ({"data": "no_such_file.csv"}, "E_DATA_UNREADABLE"),
        ({"config": "no_such_config.json"}, "E_CONFIG_UNREADABLE"),
    ],
)
def test_a_failure_prints_its_code_and_returns_non_zero(tmp_path, capsys, argv_change, expected):
    out = tmp_path / "results"
    arguments = {
        "data": str(EXAMPLE),
        "config": str(write_config(tmp_path)),
        "out": str(out),
    }
    arguments.update(argv_change)
    code = main(["--data", arguments["data"], "--config", arguments["config"],
                 "--out", arguments["out"]])
    assert code == 2
    assert expected in capsys.readouterr().err


def test_the_run_writes_nothing_outside_the_output_directory(tmp_path):
    """quickstart says so, and a program that scatters files is hard to trust."""
    out = tmp_path / "results"
    config = write_config(tmp_path)
    before = {path.name for path in tmp_path.iterdir()}
    main(["--data", str(EXAMPLE), "--config", str(config), "--out", str(out)])
    after = {path.name for path in tmp_path.iterdir()}
    assert after - before == {"results"}


# ================================================== T703: the quickstart runs

def test_the_command_the_quickstart_gives_actually_works(tmp_path):
    """The document is verified by running it, not by reading it."""
    out = tmp_path / "results"
    code = main([
        "--data", str(ROOT / "tests" / "data" / "synthetic_5K.csv"),
        "--config", str(ROOT / "configs" / "synthetic_5K.json"),
        "--out", str(out),
    ])
    assert code == 0
    for name in ("resolved_config.json", "diagnostics.csv",
                 "fit_parameters_vs_T.csv", "fit_metrics_vs_T.csv",
                 "5K_fit.csv", "multistart_5K.csv"):
        assert (out / name).exists(), name


class _ReachedTheProcedure(Exception):
    """Raised by the stand-in below, so the test sees what it was handed."""


def _capture_procedure(monkeypatch):
    """What `workflow.analyse` is called with, without running it."""
    from mbfit import workflow

    seen = {}

    def fake(path, document, mode=None, hooks=None):
        seen["path"], seen["document"], seen["mode"] = path, document, mode
        raise _ReachedTheProcedure()

    monkeypatch.setattr(workflow, "analyse", fake)
    return seen


def test_no_priors_reaches_the_procedure(tmp_path, monkeypatch):
    """FR-057. The switch has to reach the run it says it changed.

    The procedure re-resolves the document for every combination it tries, so
    it is handed a document rather than a configuration. It used to be handed
    the declared one: `--count data --no-priors` reported that the priors had
    been removed and minimised with the robust loss and the low-field emphasis
    still in force.
    """
    # The two soft priors an independent-strategy run may carry. The coupling
    # and the monotonic expectation need `global_smooth`, so they are not the
    # ones to test here.
    config = write_config(
        tmp_path,
        optimization={"multi_start": 3, "loss": "soft_l1",
                      "low_field_weight": {"enabled": True, "alpha": 5.0,
                                           "B0_T": 1.0}},
    )
    before = cfg.resolve(json.loads(config.read_text(encoding="utf-8")))
    assert before.optimization["loss"] == "soft_l1"
    assert before.optimization["low_field_weight"]["enabled"]

    seen = _capture_procedure(monkeypatch)
    with pytest.raises(_ReachedTheProcedure):
        main(["--data", str(EXAMPLE), "--config", str(config),
              "--out", str(tmp_path / "out"), "--count", "data", "--no-priors"])

    resolved = cfg.resolve(seen["document"])
    assert resolved.optimization["loss"] == "linear"
    assert not resolved.optimization["low_field_weight"]["enabled"]


def test_the_switch_alone_chooses_the_procedure(tmp_path, monkeypatch):
    """NR-005, NR-013. A document is not enough to change which run happens.

    `workflow.count` has a default, so every document that has been through
    `resolve` declares it -- and every emitted `resolved_config.json` has been.
    Reading the document instead of the switch sent a declared-carrier run's
    own emitted configuration into the procedure on the way back, which is the
    round trip NR-005 exists to protect.

    The cost is that reproducing a confirmed answer needs `--count` named
    beside the document. The README says so, because the alternative is a
    configuration file that means one thing on the page and another here.
    """
    config = write_config(tmp_path, workflow={"count": "data"})
    seen = _capture_procedure(monkeypatch)

    code = main(["--data", str(EXAMPLE), "--config", str(config),
                 "--out", str(tmp_path / "declared")])
    assert code == 0 and not seen, "a document alone must not reach the procedure"

    with pytest.raises(_ReachedTheProcedure):
        main(["--data", str(EXAMPLE), "--config", str(config),
              "--out", str(tmp_path / "procedure"), "--count", "data"])
    assert seen["mode"] == "data"


def test_the_smaller_shipped_configuration_also_runs(tmp_path):
    out = tmp_path / "results"
    assert main([
        "--data", str(EXAMPLE),
        "--config", str(ROOT / "configs" / "example_1e1h.json"),
        "--out", str(out),
    ]) == 0
