"""Uploaded tables: what was read, what it probably means, and one table out.

FR-093 to FR-096. The files a reader brings are not the project's reference
table. The twelve reference sweeps themselves arrive with three lines of commas
above the header, no temperature column, and three unnamed empty columns. Other
instruments write a semicolon and a decimal comma, UTF-16 from Excel's "Unicode
text", a unit line under the names, or `rho_xx` and `rho_xy` in separate files.
So this module reads what is there, proposes a mapping, and leaves the decision
to the reader; it never analyses a file whose mapping the reader has not
confirmed.

Units are converted here and nowhere else (FR-095). Past `combine` the analysis
sees tesla and microohm centimetres only.
"""

from __future__ import annotations

import csv
import io
import math
import re
import uuid
from dataclasses import dataclass, field

import numpy as np

from .errors import AppError

#: AC-034. Rows shown before the mapping is confirmed.
PREVIEW_ROWS = 8

FIELD_UNITS: dict[str, float] = {"T": 1.0, "mT": 1e-3, "kOe": 0.1, "Oe": 1e-4}
RESISTIVITY_UNITS: dict[str, float] = {
    "uOhm_cm": 1.0,
    "mOhm_cm": 1e3,
    "Ohm_cm": 1e6,
    "uOhm_m": 1e2,
    "Ohm_m": 1e8,
}

#: The column names of the one table handed to the analysis.
COLUMNS = {"T": "T(K)", "B": "B(T)", "rhoxx": "rhoxx(microohm cm)", "rhoxy": "rhoxy(microohm cm)"}

_TEMPERATURE_IN_NAME = re.compile(r"(?<![0-9.])(\d+(?:\.\d+)?)\s*[Kk](?![A-Za-z])")
_DECIMAL_COMMA = re.compile(r"^[-+]?\d+,\d+(?:[eE][-+]?\d+)?$")
_SPREADSHEET_SIGNATURES = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")


@dataclass(frozen=True)
class Table:
    """One uploaded file, as read."""

    file_id: str
    name: str
    skipped_lines: int
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    decimal_comma: bool = False

    def preview(self) -> dict:
        proposal = propose(self)
        return {
            "file_id": self.file_id,
            "name": self.name,
            "skipped_lines": self.skipped_lines,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows[:PREVIEW_ROWS]],
            "row_count": len(self.rows),
            "proposal": proposal,
            "temperatures": temperatures_of(self, proposal),
        }


#: More distinct temperatures than this in one file is a temperature sweep, not
#: a set of field sweeps, and listing them helps nobody.
MAX_LISTED_TEMPERATURES = 500


def temperatures_of(table: Table, proposal: dict) -> list[float]:
    """The temperatures a file holds under its proposed mapping.

    Sent with the preview so the page can see, before anything is analysed,
    that two uploads hold the same sweeps -- the reference folder carries the
    twelve files and a table of all twelve, and choosing everything in it
    otherwise fails only when the analysis is started (FR-096).
    """
    if proposal.get("T_column"):
        index = table.columns.index(proposal["T_column"])
        values = {round(v, 6) for v in (_number(row[index], table.decimal_comma)
                                        for row in table.rows) if v is not None}
        return sorted(values)[:MAX_LISTED_TEMPERATURES]
    if proposal.get("T_from_name") is not None:
        return [float(proposal["T_from_name"])]
    return []


@dataclass
class Mapping:
    """What the reader confirmed for one file. Data model 005 section 1.2.

    A file may carry `rho_xx`, `rho_xy` or both. A temperature needs both in
    the end, from one file or from two (FR-096).
    """

    file_id: str
    B: str | None = None
    rhoxx: str | None = None
    rhoxy: str | None = None
    T_column: str | None = None
    T_K: float | None = None
    field_unit: str = "T"
    resistivity_unit: str = "uOhm_cm"


@dataclass
class Combined:
    """The one table the analysis reads, and what went into it."""

    text: str
    temperatures: dict[str, list[float]] = field(default_factory=dict)
    # Temperatures whose two channels came from different files, and how many
    # field points of the Hall channel were interpolated onto the other's grid.
    merged: dict[float, int] = field(default_factory=dict)
    # FR-005. Rows discarded here, before the library ever sees them. It counts
    # its own drops from the table it reads, and these rows are not in it, so
    # counted here or counted nowhere.
    dropped: int = 0


# ------------------------------------------------------------------ reading

def decode(raw: bytes) -> str:
    """Text from bytes. Instruments on Korean Windows write cp949; Excel's
    "Unicode text" writes UTF-16."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    head = raw[:400]
    if head and head.count(b"\x00") > len(head) // 4:
        for encoding in ("utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(encoding)
            except UnicodeDecodeError:
                continue
            if "\x00" not in text:
                return text
    for encoding in ("utf-8-sig", "cp949", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("latin-1", raw, 0, 1, "unreachable")


def _number(text: str, decimal_comma: bool = False) -> float | None:
    if text is None:
        return None
    value = text.strip()
    if decimal_comma:
        value = value.replace(",", ".")
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _split(line: str, delimiter: str | None) -> list[str]:
    if delimiter is None:
        return line.split()
    return next(csv.reader([line], delimiter=delimiter))


def _delimiter(lines: list[str]) -> str | None:
    """The separator that gives the most rows of two or more cells. None is whitespace.

    A semicolon is tried before the comma, because a table written with a
    decimal comma is also a table of commas.
    """
    best, best_score = None, 0
    for candidate in ("\t", ";", ",", None):
        counts = [len([c for c in _split(line, candidate) if c.strip()]) for line in lines[:50]]
        wide = sum(1 for c in counts if c >= 2)
        if wide > best_score:
            best, best_score = candidate, wide
    return best


def _blank(cells: list[str]) -> bool:
    return not any(cell.strip() for cell in cells)


def _numeric(cells: list[str], decimal_comma: bool) -> bool:
    filled = [cell for cell in cells if cell.strip()]
    return len(filled) >= 2 and all(_number(cell, decimal_comma) is not None for cell in filled)


def parse(name: str, raw: bytes) -> Table:
    """FR-094. The header is the first row followed by numeric rows."""
    if not raw.strip():
        raise AppError("E_UPLOAD_EMPTY")
    if raw.startswith(_SPREADSHEET_SIGNATURES):
        raise AppError("E_UPLOAD_SPREADSHEET", file=name)
    try:
        text = decode(raw)
    except UnicodeDecodeError:
        raise AppError("E_UPLOAD_UNREADABLE", file=name) from None
    if "\x00" in text:
        raise AppError("E_UPLOAD_UNREADABLE", file=name)

    lines = text.splitlines()
    delimiter = _delimiter([line for line in lines if line.strip()])
    cells = [_split(line, delimiter) for line in lines]
    filled = [c.strip() for row in cells for c in row if c.strip()]
    decimal_comma = delimiter != "," and sum(1 for c in filled if _DECIMAL_COMMA.match(c)) > len(filled) // 4
    if not any(len([c for c in row if c.strip()]) >= 2 for row in cells):
        raise AppError("E_UPLOAD_UNREADABLE", file=name)

    header_at = None
    for index, row in enumerate(cells):
        if _blank(row):
            continue
        following = next((r for r in cells[index + 1:] if not _blank(r)), None)
        if _numeric(row, decimal_comma):
            header_at = index - 1          # no header: numbers from the first row
            break
        if following is not None and _numeric(following, decimal_comma):
            header_at = index
            break
    if header_at is None:
        raise AppError("E_UPLOAD_NO_TABLE", file=name)

    first_data = header_at + 1
    body_rows = [row for row in cells[first_data:] if not _blank(row)]
    width = max(len(row) for row in body_rows)
    skipped = first_data
    if header_at >= 0:
        names = [cell.strip() for cell in cells[header_at]]
        skipped = header_at
        # A name line above a unit line: "B" over "T" reads as "B [T]".
        above = header_at - 1
        while above >= 0 and _blank(cells[above]):
            above -= 1
        if above >= 0:
            upper = [cell.strip() for cell in cells[above]]
            if (not _numeric(cells[above], decimal_comma)
                    and len([c for c in upper if c]) == len([c for c in names if c])
                    and len([c for c in names if c]) >= 2
                    and all(_number(c, decimal_comma) is None for c in names if c)
                    and _looks_like_units(names)):
                names = [f"{u} [{n}]" if u and n else (u or n)
                         for u, n in zip(upper + [""] * (len(names) - len(upper)), names)]
                skipped = above
    else:
        names = []
    names = names + [""] * (width - len(names))

    body = [row + [""] * (width - len(row)) for row in body_rows]
    # A column is kept when it has a name or carries a value. The reference
    # sweeps end every row with three empty cells under empty names.
    keep = [i for i in range(width) if names[i] or any(row[i].strip() for row in body)]
    columns = []
    for i in keep:
        label = names[i] or f"column {i + 1}"
        while label in columns:
            label = f"{label} ({i + 1})"
        columns.append(label)
    rows = tuple(tuple(row[i].strip() for i in keep) for row in body)
    if not rows:
        raise AppError("E_UPLOAD_NO_TABLE", file=name)
    return Table(file_id=uuid.uuid4().hex, name=name, skipped_lines=skipped,
                 columns=tuple(columns), rows=rows, decimal_comma=decimal_comma)


_UNIT_WORDS = re.compile(r"^(t|mt|koe|oe|k|ohm|mohm|uohm|µohm|μohm|Ω|mΩ|μΩ|µΩ)([ ·*.]?(cm|m))?$", re.I)


def _looks_like_units(labels: list[str]) -> bool:
    """A line of units: short cells, at least one a recognised unit."""
    cells = [c for c in labels if c]
    return (all(len(c) <= 12 for c in cells)
            and any(_UNIT_WORDS.match(c.replace(" ", "")) for c in cells))


# ---------------------------------------------------------------- proposing

def _tokens(label: str) -> list[str]:
    return [t for t in re.split(r"[^0-9a-z]+", label.lower()) if t]


def temperature_from_name(name: str) -> float | None:
    """A number followed by K in the file name, or None. FR-094."""
    stem = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    found = _TEMPERATURE_IN_NAME.findall(stem)
    return float(found[-1]) if found else None


def propose(table: Table) -> dict:
    """A guess the reader confirms. Wrong guesses cost a click, not a result."""
    proposal = {"B": None, "rhoxx": None, "rhoxy": None, "T_column": None,
                "T_from_name": temperature_from_name(table.name),
                "field_unit": "T", "resistivity_unit": "uOhm_cm"}
    for column in table.columns:
        tokens = _tokens(column)
        joined = "".join(tokens)
        if not tokens:
            continue
        head = tokens[0]
        if proposal["rhoxy"] is None and ("xy" in joined or "yx" in joined or "hall" in joined):
            proposal["rhoxy"] = column
        elif proposal["rhoxx"] is None and "xx" in joined:
            proposal["rhoxx"] = column
        elif proposal["T_column"] is None and head in ("t", "temp", "temperature"):
            proposal["T_column"] = column
        elif proposal["B"] is None and head in ("b", "h", "field", "mu0h", "magneticfield"):
            proposal["B"] = column
            if "koe" in tokens:
                proposal["field_unit"] = "kOe"
            elif "oe" in tokens:
                proposal["field_unit"] = "Oe"
            elif "mt" in tokens:
                proposal["field_unit"] = "mT"
    resistivity = " ".join(filter(None, (proposal["rhoxx"], proposal["rhoxy"]))).lower()
    compact = re.sub(r"[^0-9a-zµμ]+", "", resistivity)
    if "mohmcm" in compact or "mΩcm" in resistivity:
        proposal["resistivity_unit"] = "mOhm_cm"
    elif "uohmm" in compact or "microohmm" in compact:
        proposal["resistivity_unit"] = "uOhm_m"
    elif "ohmm" in compact and "ohmcm" not in compact:
        proposal["resistivity_unit"] = "Ohm_m"
    elif "ohmcm" in compact and not any(p in compact for p in ("uohm", "microohm", "µohm", "μohm")):
        proposal["resistivity_unit"] = "Ohm_cm"
    return proposal


# ---------------------------------------------------------------- combining

def _column(table: Table, name: str | None, role: str, required: bool = True) -> int | None:
    if not name:
        if required:
            raise AppError("E_MAPPING_INCOMPLETE", file=table.name, missing=role)
        return None
    if name not in table.columns:
        raise AppError("E_MAPPING_UNKNOWN_COLUMN", file=table.name, column=name)
    return table.columns.index(name)


def combine(tables: dict[str, Table], mappings: list[Mapping]) -> Combined:
    """FR-095, FR-096. One table in tesla and microohm centimetres.

    Each channel of each temperature must come from exactly one file. A file
    may carry both channels, or one: `rho_xx` from one file and `rho_xy` from
    another at the same temperature are joined on the field, the Hall channel
    interpolated onto the longitudinal channel's field points within the range
    both cover. The same channel at the same temperature from two files is
    refused, naming both.
    """
    if not mappings:
        raise AppError("E_UPLOAD_EMPTY")

    # temperature -> channel -> (file name, field in T, values in microohm cm)
    channels: dict[float, dict[str, tuple[str, np.ndarray, np.ndarray]]] = {}
    together: dict[float, str] = {}
    combined = Combined(text="")

    for mapping in mappings:
        table = tables.get(mapping.file_id)
        if table is None:
            raise AppError("E_FILE_UNKNOWN", file_id=mapping.file_id)
        if mapping.field_unit not in FIELD_UNITS:
            raise AppError("E_MAPPING_BAD_UNIT", file=table.name, unit=mapping.field_unit)
        if mapping.resistivity_unit not in RESISTIVITY_UNITS:
            raise AppError("E_MAPPING_BAD_UNIT", file=table.name, unit=mapping.resistivity_unit)

        b = _column(table, mapping.B, "B")
        xx = _column(table, mapping.rhoxx, "rhoxx", required=False)
        xy = _column(table, mapping.rhoxy, "rhoxy", required=False)
        if xx is None and xy is None:
            raise AppError("E_MAPPING_INCOMPLETE", file=table.name, missing="rhoxx/rhoxy")
        t = _column(table, mapping.T_column, "T", required=False)
        if t is None and (mapping.T_K is None or not math.isfinite(float(mapping.T_K))):
            raise AppError("E_MAPPING_INCOMPLETE", file=table.name, missing="T")

        comma = table.decimal_comma
        field_factor = FIELD_UNITS[mapping.field_unit]
        rho_factor = RESISTIVITY_UNITS[mapping.resistivity_unit]
        per_T: dict[float, dict[str, list[tuple[float, float]]]] = {}
        for row in table.rows:
            T_K = _number(row[t], comma) if t is not None else float(mapping.T_K)
            B = _number(row[b], comma)
            if T_K is None or B is None:
                # A row with no temperature or no field cannot be placed at
                # all. Dropping it is right; dropping it in silence is not,
                # and a whole sweep can go this way on a file whose
                # temperature column holds a stray word (Article VI).
                combined.dropped += 1
                continue
            key = round(T_K, 6)
            slot = per_T.setdefault(key, {"xx": [], "xy": []})
            for role, index in (("xx", xx), ("xy", xy)):
                if index is None:
                    continue
                value = _number(row[index], comma)
                slot[role].append((B * field_factor, np.nan if value is None else value * rho_factor))

        for T_K, slot in per_T.items():
            for role in ("xx", "xy"):
                if not slot[role]:
                    continue
                if role in channels.get(T_K, {}):
                    raise AppError("E_TEMPERATURE_DUPLICATE", T_K=T_K,
                                   files=[channels[T_K][role][0], table.name])
                pairs = slot[role]
                channels.setdefault(T_K, {})[role] = (
                    table.name,
                    np.array([p[0] for p in pairs], dtype=float),
                    np.array([p[1] for p in pairs], dtype=float),
                )
            if slot["xx"] and slot["xy"]:
                together[T_K] = table.name
        combined.temperatures[table.name] = sorted(per_T)

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([COLUMNS["T"], COLUMNS["B"], COLUMNS["rhoxx"], COLUMNS["rhoxy"]])

    for T_K in sorted(channels):
        have = channels[T_K]
        if "xx" not in have or "xy" not in have:
            present = next(iter(have.values()))[0]
            raise AppError("E_MAPPING_INCOMPLETE", file=present, T_K=T_K,
                           missing="rhoxy" if "xy" not in have else "rhoxx")
        name_xx, B_xx, values_xx = have["xx"]
        name_xy, B_xy, values_xy = have["xy"]
        if together.get(T_K) == name_xx == name_xy and B_xx.shape == B_xy.shape:
            joined_xy = values_xy
        else:
            # Join on the field. Only the Hall points inside both files' range
            # are kept; outside it the cell is left empty and the library drops
            # the record and counts it (FR-006).
            usable = np.isfinite(values_xy)
            order = np.argsort(B_xy[usable])
            source_B, source_y = B_xy[usable][order], values_xy[usable][order]
            joined_xy = np.full(B_xx.shape, np.nan)
            if source_B.size >= 2:
                inside = (B_xx >= source_B[0]) & (B_xx <= source_B[-1])
                joined_xy[inside] = np.interp(B_xx[inside], source_B, source_y)
            combined.merged[T_K] = int(np.count_nonzero(np.isfinite(joined_xy)))
        for B, rxx, rxy in zip(B_xx, values_xx, joined_xy):
            writer.writerow([
                repr(float(T_K)), repr(float(B)),
                "" if not np.isfinite(rxx) else repr(float(rxx)),
                "" if not np.isfinite(rxy) else repr(float(rxy)),
            ])

    combined.text = out.getvalue()
    return combined
