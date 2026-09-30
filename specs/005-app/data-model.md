# Data model 005 — what feature 005 adds

> English is normative. `docs/005-data-model.ko.md` is its translation.
>
> Extends the data models of features 001 to 004. The server is a presentation
> layer, like the command line: it holds no state that outlives the process.
>
> *Amended 2026-09-19:* this note also claimed the server adds no setting to
> the configuration document. FR-112 makes a confirmed answer reproducible on
> the command line, and a coupled band had no form a document could carry, so
> `workflow.smooth_band` is declared in the data model of feature 004 beside
> `workflow.fixed_counts`. It is a setting of the procedure, reachable from
> both, which is what FR-107 requires.

---

## 1. Requests and responses

Every body is JSON except the upload and the two downloads. Every failure is
`{"code": ..., "params": {...}}` with no sentence in it (FR-105).

| Method and path | Body | Returns |
| --- | --- | --- |
| `GET /api/health` | | `{"version"}` |
| `POST /api/files` | one or more files, multipart | `{"files": [preview, ...]}` |
| `POST /api/analyses` | analysis request | `202`, `{"job_id"}` |
| `GET /api/jobs/{job_id}` | | job |
| `POST /api/jobs/{job_id}/stop` | | `202`, `{"job_id"}` |
| `POST /api/jobs/{job_id}/precise` | `{"T_K"}` | `202`, `{"job_id"}` of a new job |
| `POST /api/jobs/{job_id}/recount` | `{"temperatures", "holes", "electrons"}` | `202`, `{"job_id"}` of a new job |
| `POST /api/jobs/{job_id}/smooth` | `{"strength"}`, of a finished refit | `202`, `{"job_id"}` of a new job |
| `POST /api/jobs/{job_id}/confirm` | `{"fixed_counts", "smooth_band"}` | `202`, `{"job_id"}` of a new job |
| `GET /api/jobs/{job_id}/report.html` | | the page of FR-092 |
| `GET /api/jobs/{job_id}/tables.zip` | | the three tables of FR-091 |

### 1.1 Preview, one per uploaded file

```text
file_id          opaque identifier for this upload
name             the file name as sent
skipped_lines    lines above the header, FR-094
columns          header names, in order
rows             the first AC-034 data rows, as strings
row_count        data rows in the file
proposal
  B              column name or null
  rhoxx          column name or null
  rhoxy          column name or null
  T_column       column name or null
  T_from_name    temperature in kelvin read from the name, or null
  field_unit     proposed from the header, "T" when it names none
  resistivity_unit   proposed from the header, "uOhm_cm" when it names none
temperatures     the temperatures the file holds under the proposed mapping,
                 so the page can show two uploads holding the same sweeps (FR-096)
```

### 1.2 Analysis request

```text
files            one mapping per file
  file_id
  B, rhoxx, rhoxy          column names
  T_column                 column name, or null
  T_K                      a number, required when T_column is null
  field_unit               "T" | "mT" | "kOe" | "Oe"
  resistivity_unit         "uOhm_cm" | "mOhm_cm" | "Ohm_cm" | "uOhm_m" | "Ohm_m"
count            "data" | "peaks"; "data" when omitted (FR-099)
symmetrize_rhoxx         false unless given (FR-100)
antisymmetrize_rhoxy     false unless given (FR-100)
document         a configuration document, or null for the supplied
                 preliminary model (FR-102)
```

Conversion factors, to tesla and to microohm centimetres (FR-095):

| unit | factor | | unit | factor |
| --- | --- | --- | --- | --- |
| `T` | `1` | | `uOhm_cm` | `1` |
| `mT` | `1e-3` | | `mOhm_cm` | `1e3` |
| `kOe` | `0.1` | | `Ohm_cm` | `1e6` |
| `Oe` | `1e-4` | | `uOhm_m` | `1e2` |
| | | | `Ohm_m` | `1e8` |

### 1.3 Job

```text
job_id
kind             "analysis" | "precise" | "recount" | "smooth" | "confirm"
state            "pending" | "running" | "succeeded" | "failed" | "stopped"
progress
  stage          "prepare" | "spectrum" | "temperature" | "search" |
                 "release" | "peaks" | "fixed" | "smooth" | "resample" |
                 "beyond" | "island" | "done"
  T_K, index, total, holes, electrons, iteration, done      where they apply
error            {"code", "params"} when failed, else null
result           when succeeded, or when stopped with temperatures finished
preliminary      the carrier set that supplied the noise level (FR-102)
```

An analysis result is the report payload of FR-092 — every temperature with its
verdict, carriers, candidates and curves. A refit result (FR-109) is one entry
of that same payload: the temperature refitted at the count the reader pinned,
in the shape the page already draws, and it answers on its own: the coupling
of FR-109 is asked for separately, of a refit that has already finished, so
that a coupling which is slow or stopped never withholds the refit. A confirm
result is an analysis result, because confirming runs the procedure again
(FR-112). A precise result is one temperature:

```text
T_K, resamples, block_length, seed, lower_bound
parameters       [{name, value, low, high, sigma}], canonical order
derived          the same, for the derived quantities of FR-061
```

---

## 2. Codes

The server's own codes. Every `E_CONFIG_*` and `E_DATA_*` of data model 001
passes through unchanged.

| Code | Params | When |
| --- | --- | --- |
| `E_UPLOAD_EMPTY` | | no file, or only empty files |
| `E_UPLOAD_UNREADABLE` | `file` | not a delimited text table |
| `E_UPLOAD_NO_TABLE` | `file` | no row is followed by numeric rows |
| `E_UPLOAD_SPREADSHEET` | `file` | a spreadsheet file; save it as text, FR-096 |
| `E_FILE_UNKNOWN` | `file_id` | a mapping names an upload the server does not hold |
| `E_MAPPING_INCOMPLETE` | `file`, `missing` | a required column or the temperature is not given |
| `E_MAPPING_UNKNOWN_COLUMN` | `file`, `column` | a mapping names a column the file lacks |
| `E_MAPPING_BAD_UNIT` | `file`, `unit` | a unit outside the lists of section 1.2 |
| `E_TEMPERATURE_DUPLICATE` | `T_K`, `files` | FR-096 |
| `E_COUNT_RULE_UNKNOWN` | `count` | a count rule other than `data` or `peaks`, FR-099 |
| `E_JOB_NOT_FOUND` | `job_id` | |
| `E_JOB_NOT_FINISHED` | `job_id` | a download, a precise check or a refit before the analysis succeeded |
| `E_PRECISE_NO_ANSWER` | `T_K` | a temperature with no fit to resample, FR-101 |
| `E_PRECISE_UNKNOWN_TEMPERATURE` | `T_K` | a temperature the analysis does not hold, for a precise check or a refit |
| `E_RECOUNT_INVALID` | `holes`, `electrons`, `most` | a pinned count of no carriers at all, or of more than AC-036 allows, FR-109 |
| `E_SMOOTHING_TOO_FEW` | `given`, `needed` | a coupling asked of a band with fewer than three temperatures, which has no curvature to constrain, FR-109 |
| `E_SMOOTHING_UNKNOWN` | `smooth`, `known` | a coupling strength that is not one of those offered |
| `E_SMOOTH_NO_BAND` | | a coupling asked of a job that is not a finished refit, FR-109 |
| `E_BAND_COUNTS_DIFFER` | `counts` | a coupling over a band whose sweeps do not share one carrier count; there is nothing to couple, FR-109 |
| `E_BUDGET_EXPIRED` | `seconds` | a coupled refit abandoned at AC-039's budget |
| `E_CONFIRM_EMPTY` | | a confirm with no adjustment to confirm, FR-112 |
| `E_REQUEST_INVALID` | `fields` | a body of the wrong shape; where, never why in words |
| `E_INTERNAL` | `detail` | anything unforeseen, still as a code |

---

## 3. What the server keeps, and for how long

| What | Where | Until |
| --- | --- | --- |
| uploaded files | memory | the process ends |
| a job and its result | memory, at most the last `32` jobs | the process ends, or the job is the oldest of 33 |
| the combined table and the written tables and page | a temporary directory per job | the process ends |
| a confirmed answer: its tables, its page, its configuration document and the combined table it ran on | a temporary directory of its own job | the process ends |

Nothing is written outside the system's temporary directory.
