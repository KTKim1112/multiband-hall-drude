"""Feature 005 -- what the page reads from a file. FR-093 to FR-096. Gate 17.

The reference sweeps are the first test: they arrive with three lines of commas
above the header, three unnamed empty columns, and the temperature only in the
file name. A reader's instrument will do something else again, so the rest are
small made-up files that each break one assumption.
"""

from __future__ import annotations

import csv
import io
import pathlib

import pytest

pytest.importorskip("fastapi")

from app import tables                                   # noqa: E402
from app.errors import AppError                          # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: Sweeps in the shape an instrument writes them -- three blank lines, a header
#: naming the channels but not the temperature, trailing empty columns, the
#: temperature only in the file name -- and the table of all of them. These
#: tests are about the reader, so what matters is the shape, and
#: `tests/data/make_synthetic.py` writes it. Nothing here is measured.
EXAMPLE = ROOT / "tests" / "data" / "uploads"


def _parse(name, text):
    return tables.parse(name, text.encode("utf-8"))


def _mapping(table, **extra):
    proposal = tables.propose(table)
    fields = dict(file_id=table.file_id, B=proposal["B"], rhoxx=proposal["rhoxx"],
                  rhoxy=proposal["rhoxy"], T_column=proposal["T_column"],
                  T_K=proposal["T_from_name"])
    fields.update(extra)
    return tables.Mapping(**fields)


def _rows(combined):
    return list(csv.DictReader(io.StringIO(combined.text)))


# --------------------------------------------------------------- reading

def test_a_reference_sweep_is_read_as_it_arrives():
    table = tables.parse("5K.csv", (EXAMPLE / "5K.csv").read_bytes())
    assert table.skipped_lines == 3
    assert table.columns == ("B_T", "rho_xx_data_uohm_cm", "rho_xy_data_uohm_cm")
    assert len(table.rows) == 361
    assert table.rows[0] == ("-9", "273.044", "-71.3193")


def test_the_proposal_for_a_reference_sweep_is_complete():
    table = tables.parse("5K.csv", (EXAMPLE / "5K.csv").read_bytes())
    proposal = tables.propose(table)
    assert proposal["B"] == "B_T"
    assert proposal["rhoxx"] == "rho_xx_data_uohm_cm"
    assert proposal["rhoxy"] == "rho_xy_data_uohm_cm"
    assert proposal["T_column"] is None and proposal["T_from_name"] == 5.0


def test_the_preview_shows_ac_034_rows():
    table = tables.parse("5K.csv", (EXAMPLE / "5K.csv").read_bytes())
    preview = table.preview()
    assert len(preview["rows"]) == tables.PREVIEW_ROWS == 8
    assert preview["row_count"] == 361


def test_a_temperature_column_is_proposed():
    table = _parse("series.csv", "T(K),B(T),rhoxx,rhoxy\n5,0,1,0\n5,1,1.1,0.1\n10,0,2,0\n")
    assert tables.propose(table)["T_column"] == "T(K)"


@pytest.mark.parametrize("name, expected", [
    ("5K.csv", 5.0), ("T=12.5K_sweep.dat", 12.5), ("sample3_300k.txt", 300.0),
    ("run 7.csv", None), ("B-sweep.csv", None),
])
def test_the_temperature_is_read_from_a_name(name, expected):
    assert tables.temperature_from_name(name) == expected


def test_tab_and_whitespace_tables_are_read():
    tab = _parse("a 2K.txt", "field\trho_xx\trho_xy\n0\t1\t0\n1\t1.1\t0.2\n")
    assert tab.columns == ("field", "rho_xx", "rho_xy")
    spaced = _parse("b 2K.txt", "# comment line\nB  Rxx  Rxy\n0  1  0\n1  1.1  0.2\n")
    assert spaced.skipped_lines == 1 and len(spaced.rows) == 2


def test_a_headerless_table_gets_numbered_columns():
    table = _parse("c 3K.csv", "0,1,0\n1,1.1,0.2\n")
    assert table.columns == ("column 1", "column 2", "column 3")
    assert len(table.rows) == 2


def test_a_cp949_file_is_read():
    raw = "자기장,rho_xx,rho_xy\n0,1,0\n1,1.1,0.2\n".encode("cp949")
    assert tables.parse("d 4K.csv", raw).columns[0] == "자기장"


@pytest.mark.parametrize("raw, code", [
    (b"", "E_UPLOAD_EMPTY"),
    (b"only,text,here\nand,more,text\n", "E_UPLOAD_NO_TABLE"),
    (b"\x00\x01\x02 binary", "E_UPLOAD_UNREADABLE"),
])
def test_what_cannot_be_read_says_so_with_a_code(raw, code):
    with pytest.raises(AppError) as caught:
        tables.parse("x.csv", raw)
    assert caught.value.code == code


# ------------------------------------------------------------- combining

def test_units_are_converted_at_the_boundary():
    """FR-095. kOe and milliohm centimetres in; tesla and microohm centimetres out."""
    table = _parse("e 5K.csv", "H(kOe),rho_xx(mOhm cm),rho_xy(mOhm cm)\n10,0.002,0.0005\n")
    mapping = _mapping(table, field_unit="kOe", resistivity_unit="mOhm_cm")
    row = _rows(tables.combine({table.file_id: table}, [mapping]))[0]
    assert float(row["B(T)"]) == pytest.approx(1.0)
    assert float(row["rhoxx(microohm cm)"]) == pytest.approx(2.0)
    assert float(row["rhoxy(microohm cm)"]) == pytest.approx(0.5)
    assert float(row["T(K)"]) == 5.0


def test_the_units_proposed_follow_the_header():
    table = _parse("f 5K.csv", "H (kOe),rho_xx (mOhm cm),rho_xy (mOhm cm)\n10,0.002,0.0005\n")
    proposal = tables.propose(table)
    assert proposal["field_unit"] == "kOe"
    assert proposal["resistivity_unit"] == "mOhm_cm"


def test_an_unreadable_cell_is_left_for_the_library_to_count():
    table = _parse("g 5K.csv", "B,rho_xx,rho_xy\n0,1,0\n1,n/a,0.2\n2,1.2,0.4\n")
    rows = _rows(tables.combine({table.file_id: table}, [_mapping(table)]))
    assert len(rows) == 3 and rows[1]["rhoxx(microohm cm)"] == ""


@pytest.mark.parametrize("change, code", [
    (dict(B=None), "E_MAPPING_INCOMPLETE"),
    (dict(T_K=None), "E_MAPPING_INCOMPLETE"),
    (dict(rhoxy="nope"), "E_MAPPING_UNKNOWN_COLUMN"),
    (dict(field_unit="gauss"), "E_MAPPING_BAD_UNIT"),
    (dict(resistivity_unit="ohm"), "E_MAPPING_BAD_UNIT"),
])
def test_an_incomplete_mapping_starts_nothing(change, code):
    """FR-094. No analysis while any file lacks a complete mapping."""
    table = _parse("h 5K.csv", "B,rho_xx,rho_xy\n0,1,0\n1,1.1,0.2\n")
    with pytest.raises(AppError) as caught:
        tables.combine({table.file_id: table}, [_mapping(table, **change)])
    assert caught.value.code == code


def test_a_row_with_no_temperature_or_field_is_counted_and_not_only_dropped():
    """FR-005, Article VI. Dropping these rows is right; dropping them in
    silence is not.

    They are taken out before the combined table is written, so the count the
    library keeps of what *it* dropped cannot see them -- counted here or
    counted nowhere. A file whose temperature column holds a stray word can
    lose a whole sweep this way and still report nothing missing.
    """
    table = _parse("mixed.csv",
                   "T,B,rho_xx,rho_xy\n5,0,1,0\n5,,1,0\nnope,1,1,0\n5,1,1.1,0.2\n")
    combined = tables.combine({table.file_id: table}, [tables.Mapping(
        file_id=table.file_id, B="B", rhoxx="rho_xx", rhoxy="rho_xy", T_column="T")])
    assert combined.dropped == 2
    assert combined.temperatures, "the readable rows still make a sweep"


def test_a_clean_file_reports_nothing_dropped():
    """The counter must not cry wolf: a reader who sees it must be able to act."""
    table = _parse("clean.csv", "T,B,rho_xx,rho_xy\n5,0,1,0\n5,1,1.1,0.2\n")
    combined = tables.combine({table.file_id: table}, [tables.Mapping(
        file_id=table.file_id, B="B", rhoxx="rho_xx", rhoxy="rho_xy", T_column="T")])
    assert combined.dropped == 0


def test_a_mapping_to_an_upload_the_server_does_not_hold_is_refused():
    with pytest.raises(AppError) as caught:
        tables.combine({}, [tables.Mapping(file_id="gone", B="B", rhoxx="x", rhoxy="y", T_K=5)])
    assert caught.value.code == "E_FILE_UNKNOWN"


def test_a_temperature_in_two_files_is_refused_naming_both():
    """FR-096. Never merged, never overwritten."""
    one = _parse("5K.csv", "B,rho_xx,rho_xy\n0,1,0\n1,1.1,0.2\n")
    two = _parse("5K again.csv", "B,rho_xx,rho_xy\n0,1,0\n1,1.1,0.2\n")
    with pytest.raises(AppError) as caught:
        tables.combine({one.file_id: one, two.file_id: two}, [_mapping(one), _mapping(two)])
    assert caught.value.code == "E_TEMPERATURE_DUPLICATE"
    assert caught.value.params["files"] == ["5K.csv", "5K again.csv"]


def test_a_semicolon_table_with_decimal_commas_is_read():
    table = _parse("s 5K.csv", "B;rho_xx;rho_xy\n-1,5;1,02;-0,075\n0,0;1,00;0,0\n1,5;1,02;0,075\n")
    assert table.decimal_comma and table.columns == ("B", "rho_xx", "rho_xy")
    row = _rows(tables.combine({table.file_id: table}, [_mapping(table)]))[0]
    assert float(row["B(T)"]) == -1.5 and float(row["rhoxx(microohm cm)"]) == 1.02


def test_a_utf16_file_from_excel_is_read():
    raw = "B\trho_xx\trho_xy\n0\t1\t0\n1\t1.1\t0.2\n".encode("utf-16")
    assert tables.parse("u 5K.txt", raw).columns == ("B", "rho_xx", "rho_xy")


def test_a_spreadsheet_is_refused_with_its_own_code():
    with pytest.raises(AppError) as caught:
        tables.parse("sheet 5K.xlsx", b"PK\x03\x04" + b"\x00" * 64)
    assert caught.value.code == "E_UPLOAD_SPREADSHEET"


def test_a_unit_line_under_the_names_is_joined_to_them():
    table = _parse("n 5K.csv", "B,rho_xx,rho_xy\nT,uOhm cm,uOhm cm\n0,1,0\n1,1.1,0.2\n")
    assert table.columns == ("B [T]", "rho_xx [uOhm cm]", "rho_xy [uOhm cm]")
    proposal = tables.propose(table)
    assert (proposal["B"], proposal["rhoxx"], proposal["rhoxy"]) == table.columns


def test_the_two_channels_may_come_from_two_files():
    """FR-096. rho_xx and rho_xy in separate files at the same temperature are joined
    on the field; rho_xy is interpolated onto rho_xx's field points."""
    xx = _parse("Rxx 5K.csv", "B,rho_xx\n-1,1.02\n0,1.00\n1,1.02\n")
    xy = _parse("Rxy 5K.csv", "B,rho_xy\n-1.0,-0.10\n-0.5,-0.05\n0.5,0.05\n1.0,0.10\n")
    assert len(xx.columns) == 2
    combined = tables.combine({xx.file_id: xx, xy.file_id: xy}, [_mapping(xx), _mapping(xy)])
    rows = _rows(combined)
    assert [float(r["B(T)"]) for r in rows] == [-1.0, 0.0, 1.0]
    assert [float(r["rhoxy(microohm cm)"]) for r in rows] == pytest.approx([-0.10, 0.0, 0.10])
    assert combined.merged == {5.0: 3}


def test_a_temperature_with_one_channel_only_is_refused():
    xx = _parse("Rxx 5K.csv", "B,rho_xx\n-1,1.02\n0,1.00\n1,1.02\n")
    with pytest.raises(AppError) as caught:
        tables.combine({xx.file_id: xx}, [_mapping(xx)])
    assert caught.value.code == "E_MAPPING_INCOMPLETE"
    assert caught.value.params["missing"] == "rhoxy"


def test_the_preview_lists_the_temperatures_a_file_holds():
    """So the page can see two uploads holding the same sweeps before anything
    is analysed: the reference folder holds the twelve files and their table."""
    one = tables.parse("5K.csv", (EXAMPLE / "5K.csv").read_bytes())
    assert one.preview()["temperatures"] == [5.0]
    table = tables.parse("all_temperatures.csv", (EXAMPLE / "all_temperatures.csv").read_bytes())
    assert table.preview()["temperatures"] == [5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0,
                                               70.0, 80.0, 90.0, 100.0, 120.0]


def test_the_twelve_reference_files_combine_to_the_reference_table():
    """The same numbers as `all_temperatures.csv`, which the command line reads."""
    names = sorted(p.name for p in EXAMPLE.glob("*K.csv"))
    assert len(names) == 12
    held, mappings = {}, []
    for name in names:
        table = tables.parse(name, (EXAMPLE / name).read_bytes())
        held[table.file_id] = table
        mappings.append(_mapping(table))
    combined = _rows(tables.combine(held, mappings))

    with open(EXAMPLE / "all_temperatures.csv", newline="", encoding="utf-8") as handle:
        reference = list(csv.DictReader(handle))
    key = lambda r: (float(r["T(K)"]), float(r["B(T)"]))           # noqa: E731
    ours = {key(r): (float(r["rhoxx(microohm cm)"]), float(r["rhoxy(microohm cm)"])) for r in combined}
    theirs = {key(r): (float(r["rhoxx(microohm cm)"]), float(r["rhoxy(microohm cm)"])) for r in reference}
    assert ours == theirs
