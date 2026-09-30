"""Every E_CONFIG_* code, and the promises the schema makes.

Article IV in practice: each test asserts on the code and never on the
wording, so the Korean in `messages.py` can be rewritten without touching a
line here.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re

import pytest

from mbfit import config as cfg
from mbfit.core.errors import MbfitError

MINIMAL = {
    "schema_version": "1.0",
    "columns": {"T": "T(K)", "B": "B(T)", "rhoxx": "rxx", "rhoxy": "rxy"},
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
}


def document(**changes):
    out = copy.deepcopy(MINIMAL)
    out.update(copy.deepcopy(changes))
    return out


def raises(code):
    return pytest.raises(MbfitError, match=code)


# ------------------------------------------------------------------ loading

def test_E_CONFIG_UNREADABLE_for_a_missing_file(tmp_path):
    with raises("E_CONFIG_UNREADABLE"):
        cfg.load_document(tmp_path / "absent.json")


def test_E_CONFIG_UNREADABLE_for_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")
    with raises("E_CONFIG_UNREADABLE"):
        cfg.load_document(path)


def test_E_CONFIG_UNREADABLE_when_the_document_is_not_an_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with raises("E_CONFIG_UNREADABLE"):
        cfg.load_document(path)


def test_a_valid_document_loads_and_resolves(tmp_path):
    path = tmp_path / "good.json"
    path.write_text(json.dumps(MINIMAL), encoding="utf-8")
    resolved = cfg.resolve(cfg.load_document(path))
    assert [c.name for c in resolved.carriers] == ["e1", "h1"]


# --------------------------------------------------------------- the schema

def test_E_CONFIG_SCHEMA_VERSION_when_absent_or_unsupported():
    missing = document()
    del missing["schema_version"]
    with raises("E_CONFIG_SCHEMA_VERSION"):
        cfg.resolve(missing)
    with raises("E_CONFIG_SCHEMA_VERSION"):
        cfg.resolve(document(schema_version="2.0"))


@pytest.mark.parametrize(
    "changes",
    [
        {"smooting": {}},                                   # top level typo
        {"smoothing": {"lambda_denisty": 1.0}},             # nested typo
        {"optimization": {"low_field_weight": {"alfa": 1}}},  # deeper typo
    ],
)
def test_E_CONFIG_UNKNOWN_FIELD_is_rejected_not_ignored(changes):
    """A misspelled option must not quietly leave a default in force."""
    with raises("E_CONFIG_UNKNOWN_FIELD"):
        cfg.resolve(document(**changes))


# --------------------------------------------- the documents the docs teach

WALKTHROUGH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "walkthrough.ko.md"


def test_every_configuration_example_in_the_walkthrough_resolves():
    """A document the walkthrough tells the reader to write must be accepted.

    FR-090 shipped with a walkthrough example that raised
    `E_CONFIG_UNKNOWN_FIELD` on every temperature key, and nothing caught it
    because no test read the walkthrough. The examples are fragments meant to
    be pasted into a document, so each is merged onto a working one.
    """
    if not WALKTHROUGH.is_file():
        pytest.skip("walkthrough not present")
    blocks = re.findall(r"```json\n(.*?)```", WALKTHROUGH.read_text(encoding="utf-8"), re.S)
    assert len(blocks) >= 5, "the walkthrough stopped showing configuration documents"
    for index, block in enumerate(blocks):
        body = block.strip()
        fragment = json.loads(body if body.startswith("{") else "{" + body.rstrip(",") + "}")
        merged = dict(MINIMAL)
        merged.update(fragment)
        try:
            cfg.resolve(copy.deepcopy(merged))
        except MbfitError as error:
            raise AssertionError(
                f"walkthrough example {index} ({sorted(fragment)}) is rejected: "
                f"{error.code}") from None


# ------------------------------------------------------ pinned counts, FR-090

def test_fixed_counts_accepts_a_temperature_and_a_range():
    """FR-090 by the command line, which raised a code for every document.

    The keys are temperatures the reader chose, and the general rule checks a
    section's keys against its defaults -- empty here by construction -- so
    every key was an unknown field, the walkthrough's own example included.
    """
    resolved = cfg.resolve(document(workflow={
        "fixed_counts": {"5": [2, 2], "10": [2, 2], "80-120": [1, 1]}}))
    assert resolved.workflow["fixed_counts"] == {
        "5": [2, 2], "10": [2, 2], "80-120": [1, 1]}


def test_fixed_counts_is_still_empty_by_default():
    assert cfg.resolve(document()).workflow["fixed_counts"] == {}


@pytest.mark.parametrize("key", ["", "warm", "5-", "-", "70-5", "5-10-20"])
def test_fixed_counts_rejects_a_key_that_names_no_temperature(key):
    """A key that pins nothing must not pass as one that pins something."""
    with raises("E_CONFIG_BAD_VALUE"):
        cfg.resolve(document(workflow={"fixed_counts": {key: [2, 2]}}))


@pytest.mark.parametrize(
    "value",
    [[2], [2, 2, 2], [2, -1], [0, 0], [2.5, 1], [True, 1], [5, 4], "2,2", 4],
)
def test_fixed_counts_rejects_a_count_that_is_not_two_whole_carriers(value):
    """`[5, 4]` is nine carriers: past the reach of a sweep, however meant."""
    with raises("E_CONFIG_BAD_VALUE"):
        cfg.resolve(document(workflow={"fixed_counts": {"50": value}}))


def test_E_CONFIG_UNKNOWN_FIELD_for_an_unknown_column_key():
    columns = dict(MINIMAL["columns"])
    columns["Hall"] = "rxy"
    with raises("E_CONFIG_UNKNOWN_FIELD"):
        cfg.resolve(document(columns=columns))


def test_E_CONFIG_UNKNOWN_FIELD_for_an_unknown_carrier_key():
    carriers = copy.deepcopy(MINIMAL["carriers"])
    carriers[0]["effective_mass"] = 0.2
    with raises("E_CONFIG_UNKNOWN_FIELD"):
        cfg.resolve(document(carriers=carriers))


def test_E_CONFIG_MISSING_FIELD_for_columns_and_carriers():
    without_columns = document()
    del without_columns["columns"]
    with raises("E_CONFIG_MISSING_FIELD"):
        cfg.resolve(without_columns)

    without_carriers = document()
    del without_carriers["carriers"]
    with raises("E_CONFIG_MISSING_FIELD"):
        cfg.resolve(without_carriers)


def test_E_CONFIG_MISSING_FIELD_names_every_missing_column():
    columns = {"T": "T(K)", "B": "B(T)"}
    with pytest.raises(MbfitError) as caught:
        cfg.resolve(document(columns=columns))
    assert caught.value.code == "E_CONFIG_MISSING_FIELD"
    assert set(caught.value.detail["missing"]) == {"rhoxx", "rhoxy"}


@pytest.mark.parametrize(
    "changes",
    [
        {"optimization": {"fit_mode": "rho_xx"}},
        {"optimization": {"fit_space": "conductivity"}},
        {"optimization": {"temperature_strategy": "global"}},
        {"optimization": {"loss": "l2"}},
        {"optimization": {"multi_start": 0}},
        {"model": {"hall_polarity": 0.5}},
        {"smoothing": {"order": 3}},
        {"smoothing": {"lambda_density": -1.0}},
        {"acceptance": {"jump_factor": 0.0}},
        {"output": {"plot_dpi": 0}},
    ],
)
def test_E_CONFIG_BAD_VALUE_outside_the_allowed_set_or_range(changes):
    with raises("E_CONFIG_BAD_VALUE"):
        cfg.resolve(document(**changes))


# ---------------------------------------------------------------- carriers

def test_E_CONFIG_NO_CARRIERS_for_an_empty_list():
    with raises("E_CONFIG_NO_CARRIERS"):
        cfg.resolve(document(carriers=[]))


def test_E_CONFIG_DUPLICATE_CARRIER():
    carriers = copy.deepcopy(MINIMAL["carriers"])
    carriers[1]["name"] = "e1"
    with raises("E_CONFIG_DUPLICATE_CARRIER"):
        cfg.resolve(document(carriers=carriers))


def test_E_CONFIG_BAD_CARRIER_KIND():
    carriers = copy.deepcopy(MINIMAL["carriers"])
    carriers[0]["kind"] = "positron"
    with raises("E_CONFIG_BAD_CARRIER_KIND"):
        cfg.resolve(document(carriers=carriers))


@pytest.mark.parametrize("bounds", [
    {"init": 1e19, "min": 0.0, "max": 1e22},      # NR-001: zero is not positive
    {"init": 1e19, "min": -1e16, "max": 1e22},
    {"init": 1e19, "min": 1e22, "max": 1e16},     # min above max
])
def test_E_CONFIG_BOUNDS_INVALID(bounds):
    carriers = copy.deepcopy(MINIMAL["carriers"])
    carriers[0]["density"] = bounds
    with raises("E_CONFIG_BOUNDS_INVALID"):
        cfg.resolve(document(carriers=carriers))


def test_E_CONFIG_INIT_OUT_OF_BOUNDS_is_caught_before_fitting():
    """FR-015. The prototype clipped silently; this refuses."""
    carriers = copy.deepcopy(MINIMAL["carriers"])
    carriers[0]["mobility"] = {"init": 1e6, "min": 1.0, "max": 50000.0}
    with pytest.raises(MbfitError) as caught:
        cfg.resolve(document(carriers=carriers))
    assert caught.value.code == "E_CONFIG_INIT_OUT_OF_BOUNDS"
    assert "mobility" in caught.value.detail["path"]


@pytest.mark.parametrize("section", ["initial_by_temperature", "overrides_by_temperature"])
def test_E_CONFIG_UNKNOWN_CARRIER_in_a_per_temperature_section(section):
    entry = {"5": {"e9": {"density": 1e19}}}
    if section == "overrides_by_temperature":
        entry = {"5": {"e9": {"density": {"min": 1e18}}}}
    with raises("E_CONFIG_UNKNOWN_CARRIER"):
        cfg.resolve(document(**{section: entry}))


def test_per_temperature_sections_accept_what_they_are_for():
    resolved = cfg.resolve(
        document(
            initial_by_temperature={"5": {"e1": {"density": 1.4e19, "mobility": 6100.0}}},
            overrides_by_temperature={"60": {"h1": {"density": {"min": 1e18, "max": 1e21}}}},
        )
    )
    assert resolved.initial_by_temperature["5"]["e1"]["mobility"] == 6100.0
    assert resolved.overrides_by_temperature["60"]["h1"]["density"]["max"] == 1e21


# ------------------------------------------- seeding is not coupling, FR-024

@pytest.mark.parametrize("strategy", ["independent", "sequential"])
@pytest.mark.parametrize(
    "prior",
    [{"smoothing": {"enabled": True}}, {"monotonic_penalty": {"enabled": True}}],
)
def test_E_CONFIG_COUPLING_WITHOUT_GLOBAL(strategy, prior):
    """A penalty coupling the temperatures needs them to be one problem."""
    changes = dict(prior)
    changes["optimization"] = {"temperature_strategy": strategy}
    with raises("E_CONFIG_COUPLING_WITHOUT_GLOBAL"):
        cfg.resolve(document(**changes))


def test_coupling_is_accepted_with_the_global_strategy():
    resolved = cfg.resolve(
        document(
            optimization={"temperature_strategy": "global_smooth"},
            smoothing={"enabled": True, "lambda_density": 1.0},
        )
    )
    assert resolved.smoothing["enabled"] is True


def test_E_CONFIG_BREAK_OUTSIDE_RANGE():
    resolved = cfg.resolve(
        document(
            optimization={"temperature_strategy": "global_smooth"},
            smoothing={"enabled": True, "breaks_K": [95.0]},
        )
    )
    cfg.validate_against_temperatures(resolved, [5.0, 100.0, 150.0])  # inside: fine
    with raises("E_CONFIG_BREAK_OUTSIDE_RANGE"):
        cfg.validate_against_temperatures(resolved, [5.0, 20.0, 60.0])


# ------------------------------------------------------------------ defaults

def test_every_default_is_inert():
    """A document declaring only columns and carriers gets stage A."""
    resolved = cfg.resolve(document())
    assert resolved.optimization["temperature_strategy"] == "independent"
    assert resolved.smoothing["enabled"] is False
    assert resolved.smoothing["lambda_density"] == 0.0
    assert resolved.smoothing["lambda_mobility"] == 0.0
    assert resolved.monotonic_penalty["enabled"] is False
    assert resolved.optimization["low_field_weight"]["enabled"] is False
    assert resolved.optimization["fit_field_range"]["enabled"] is False
    assert resolved.optimization["loss"] == "linear"
    assert resolved.model["hall_polarity"] == 1.0


def test_the_resolved_document_round_trips_exactly():
    """FR-037: what is written out reproduces the run."""
    once = cfg.resolve(document(optimization={"multi_start": 3, "random_seed": 7}))
    twice = cfg.resolve(once.as_document())
    assert twice.as_document() == once.as_document()


def test_free_parameters_and_channels_are_counted_for_FR006():
    both = cfg.resolve(document())
    assert both.n_free_parameters == 4
    assert both.n_channels == 2
    single = cfg.resolve(document(optimization={"fit_mode": "rhoxy"}))
    assert single.n_channels == 1


# ----------------------------------------------------- the FR-057 switch

def test_disable_soft_priors_removes_exactly_the_soft_ones():
    declared = cfg.resolve(
        document(
            optimization={
                "temperature_strategy": "global_smooth",
                "loss": "soft_l1",
                "low_field_weight": {"enabled": True, "alpha": 5.0},
                "fit_field_range": {"enabled": True, "abs_max_T": 6.0},
            },
            smoothing={"enabled": True, "lambda_density": 1.0},
            monotonic_penalty={"enabled": True},
        )
    )
    stripped = cfg.disable_soft_priors(declared)

    # C3 to C6, the soft priors, are gone.
    assert stripped.smoothing["enabled"] is False
    assert stripped.monotonic_penalty["enabled"] is False
    assert stripped.optimization["low_field_weight"]["enabled"] is False
    assert stripped.optimization["loss"] == "linear"

    # C2 and C7, the hard constraints, are untouched: they declare the
    # admissible domain rather than a preference within it.
    assert stripped.optimization["fit_field_range"]["enabled"] is True
    assert stripped.optimization["fit_field_range"]["abs_max_T"] == 6.0
    assert stripped.carriers == declared.carriers

    # And the declared strengths survive, so the record says what was asked.
    assert stripped.smoothing["lambda_density"] == 1.0


def test_a_stripped_configuration_reproduces_without_the_switch():
    """FR-037 records what was in force, not what was declared."""
    declared = cfg.resolve(
        document(
            optimization={"temperature_strategy": "global_smooth"},
            smoothing={"enabled": True, "lambda_mobility": 2.0},
        )
    )
    stripped = cfg.disable_soft_priors(declared)
    again = cfg.resolve(stripped.as_document())
    assert again.as_document() == stripped.as_document()
    assert again.smoothing["enabled"] is False
