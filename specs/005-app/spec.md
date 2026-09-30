# Feature 005 — the program for a reader who does not run commands

> English is normative. `docs/005-spec.ko.md` is its translation.
>
> Requirement identifiers continue the project numbering: FR-093 follows
> FR-092, and nothing already issued is reused or renumbered.

---

## 1. Purpose

Features 001 to 004 are a library and a command line. That serves a reader who
installs an interpreter, writes a configuration document by hand and reads
tables. **The colleagues this program is now for do none of those.** They have
a folder of sweeps, a browser, and no administrator rights.

This feature puts the procedure of feature 004 behind a page served on their
own machine, and packs the page, the server and the analysis into one folder
that runs by double-click. It adds no physics. Every number on the page is a
number the command line would have printed for the same data.

---

## 2. Who uses it and what they need

An experimental physicist with sweeps exported from their own instrument. The
files will not look like the project's reference table: a few blank or text
lines above the header, no temperature column because the temperature is in
the file name, resistivity in whatever unit the instrument wrote.

They need the program to show them what it read before it analyses anything;
to tell them plainly how the carriers are counted and what the answer can
claim; to tell them how far a
long run has got and let them stop it; and to show the verdict before the
numbers, exactly as the report of FR-092 does.

---

## 3. Terms

| Term | Meaning here |
| --- | --- |
| **file** | one uploaded table, holding one temperature or several |
| **mapping** | which column of a file is the field, which the two resistivities, and where its temperature comes from |
| **job** | one analysis or one resampling, running in the background |
| **fast check** | the procedure of feature 004 over every temperature, with no resampling |
| **precise check** | resampling, for one temperature the reader picks, after a fast check |

---

## 4. Functional requirements

### 4.1 Getting the data in

- **FR-093** The page shall accept several files for one analysis, each holding
  one temperature or several.
- **FR-094** Before any analysis the page shall show the first rows of every
  file together with a proposed mapping, and the reader shall confirm or correct
  it. The header is the first row that is followed by numeric rows; the lines
  above it are skipped and their number is shown. A temperature comes either
  from a column or, when there is none, from a number followed by `K` in the
  file name. **No analysis shall start while any file lacks a complete
  mapping.**
- **FR-095** The reader shall declare the unit of the field and of the
  resistivity for each file from a fixed list, and the conversion shall happen
  at one boundary. Past that boundary the analysis sees tesla and microohm
  centimetres and nothing else.
- **FR-096** Each channel of each temperature shall come from exactly one
  file. A file may carry `rho_xx`, `rho_xy` or both; when the two channels of a
  temperature come from two files they shall be joined on the field, the Hall
  channel interpolated onto the longitudinal channel's field points within the
  range both cover. The same channel at one temperature from two files shall be
  refused, naming both files, and not merged, averaged or silently overwritten:
  two sweeps of one channel at one temperature are either a duplicate upload or
  two measurements, and only the reader knows which. A spreadsheet file shall be
  refused with its own code, saying to save it as text. *Amended 2026-09-16:*
  first written for one file per temperature carrying both channels; readers'
  instruments also write the channels separately, a semicolon with a decimal
  comma, UTF-16, and a unit line under the names, and all of those are read.

### 4.2 Running

- **FR-097** An analysis shall run in the background. The page shall show which
  temperature of how many is being analysed and which combination is being
  fitted, and no request shall be held open for the length of the analysis.
- **FR-098** A running job shall be stoppable. The stop shall take effect
  before the next fit starts, shall be reported as stopped and never as failed,
  and every temperature that finished before it shall be kept and shown.
- **FR-099** The page shall run the data rule of FR-080 and shall state what its
  answer can claim: a lower bound on the conduction channels a sweep requires,
  with their effective densities and mobilities. The peaks rule, whose count
  needs evidence from outside transport before it is quoted, shall stay on the
  command line and off the page. *Amended 2026-09-16:* the page first offered
  both rules with the data rule preselected; a reader of the page is served by
  one procedure explained plainly.
- **FR-100** The two symmetrisation switches of FR-008 and FR-009 shall be on
  the page and off until the reader turns them on.
- **FR-101** After a fast check the reader shall be able to request a precise
  check for one temperature at a time, as its own job that shows its progress
  and can be stopped. A stopped precise check keeps nothing: an interval from a
  fraction of the resamples is a different interval, not an early look at the
  same one. Both count rules end in a fit, so
  either answer can be resampled; a temperature where the peaks rule found
  nothing to fit cannot.
- **FR-102** The spectrum's noise level is taken from the residual of a
  preliminary fit (feature 003). A reader of the page declares no carriers, so
  the program shall supply the preliminary model, shall say on the page which
  model it supplied, and shall accept a configuration document in its place.

### 4.3 Showing

- **FR-103** The first thing shown for a finished analysis shall be the verdict
  per temperature — combination, grade, gates failed, carriers outside the
  window, and under the peaks rule why its loop
  stopped — in the order of FR-092.
  Measurement against model, parameters against temperature and the
  combinations tried follow.
- **FR-104** The tables of FR-091 and the page of FR-092 shall be downloadable
  from a finished analysis, and shall be the same files the command line writes
  for the same data and settings.
- **FR-105** The server shall return codes and parameters, never sentences
  (Article IV). Every sentence on screen shall come from one table of labels in
  the page's own source, keyed by those codes.

### 4.4 Delivering

- **FR-106** The program shall be deliverable as one folder that runs on a
  Windows machine with no interpreter installed and no administrator rights. It
  shall serve on the loopback interface only, shall open the browser once the
  server answers and not before, and shall keep a console window open as the
  way to stop it. It shall serve on the address of its previous run when that
  address is free, and on one the operating system chooses otherwise, so that a
  window the reader left open from the previous run reaches the program again.
- **FR-107** The command line shall remain complete. Nothing the page does
  shall be unreachable without it, and the tests of features 001 to 004 shall
  keep running against the library and not through the page.
- **FR-109** After an analysis has finished, the reader shall be able to refit
  any one of its temperatures, or any band of them, at a carrier count they
  choose, without running the analysis again. The band is the case that
  matters and one temperature is the band of length one: FR-090 exists because
  `n(T)` cannot be plotted across a model that changes underneath it, and one
  carrier set over one sweep settles nothing about a series. It shall use the same routine as the count pinning of
  FR-090, so that the page and the command line answer the same question the
  same way. The verdict the procedure reached shall be left standing beside the
  refit, and what the chosen count cost or gained in residual shall be
  reported: a reader who overrides the count must be able to see the price of
  the override, not only its result. The refit shall reach the figures and the
  tables the analysis is read from, beside the answer the procedure reached and
  never in place of it: the parameters against temperature, the model against
  the measurement, and the carrier values at each temperature. A refit shown
  only as a verdict is a refit the reader cannot check, and `n(T)` is the plot
  FR-090 exists for.

  A band held to one count shall also report **how far it is from a smooth
  series**, in the measure the coupling penalty of FR-027 acts on, and the
  reader shall be able to ask for that coupling at one of the declared
  strengths. It shall be off unless asked for, it shall be refused on a band of
  fewer than three temperatures — a curvature needs three points — and what it
  cost in residual shall be reported per temperature. The measure itself is
  not the page's: the command line shall report the roughness of the band it
  ran, from the same routine, so that FR-107 holds for it as for everything
  else. No strength is free, and
  a large price is evidence that the model changes across the band: that is a
  reason to divide the band, not to press harder.

  *Amended 2026-09-19:* the refit and the coupling were first offered as one
  request, and the answer to both was withheld until both had finished. A
  coupling over a long band takes far longer than the refits it follows, so
  asking for one hid the refit that was already complete, and the reader saw a
  page that did nothing for hours. They shall be asked for separately: the
  refit shall answer on its own, and the coupling shall be asked of that
  answer. A coupling that is stopped shall leave the refit standing. Both shall
  report which temperature they are working on, and both shall be stoppable.

  *Amended 2026-09-20:* a pinned refit shall not be held to the budget that
  prunes the search. That budget exists to cut short combinations nobody asked
  for; a pinned count is asked for, and cutting it short answers the reader
  with silence. Measured on this project's sweeps, one starting point of a
  six-carrier fit took `231` s at 70 K and `52` s at 5 K against the `2.5` s
  the search allows it, so `3h+3e` returned nothing at 5, 30 and 70 K — at 70 K
  every combination of six carriers or more returned nothing. A refit shall
  have its own budget and its own count of starting points (AC-041, AC-042).
  Where even that is not enough, the sweeps the count could not be fitted at
  shall be **named**: they shall not be folded into the answer, entered among
  the adjustments, or carried into a confirmed document. Returning the count
  the reader overrode, and saying nothing, reports a refit that did not happen.
- **FR-110** The page shall be able to show, for each temperature, the mobility
  spectrum that bounded its search: the distribution for each carrier sign, the
  peaks found in it, and the mobility window those were turned into. It shall
  be folded away until asked for, so that the verdict remains what the page
  leads with (FR-103). It shall say what the vertical axis is — the normalised
  weight the spectrum solves for, not a carrier density — because a reader who
  takes it for a density will read a peak height as a carrier count. The report
  of FR-092 shall carry and draw the same spectrum, folded away in the same
  manner: it is the file a reader downloads and sends on, and a bound that
  cannot be looked at in it is a bound taken on trust (FR-107).
- **FR-111** The reader shall be able to choose the language of the page
  between Korean and English, and the choice shall be remembered. Every
  sentence of a language shall live in one place and nowhere else, and a
  sentence one language has while the other does not shall fail the build
  rather than reach a reader: a translation that can fall behind silently is a
  translation that will.
- **FR-112** The adjustments of FR-109 shall have a place of their own,
  separate from where the procedure's own answer is read, and reached only
  after an analysis has finished. Adjustments shall **accumulate**: each covers
  the temperatures it names and leaves the rest as the procedure decided them,
  so that a series can be repaired a temperature at a time; where two cover one
  temperature, the later stands. The accumulated answer shall be shown beside
  the procedure's, under FR-109's rule that the procedure's answer is left
  standing.

  The reader shall be able to **confirm** the accumulated answer. Confirming
  shall run the procedure again under the settings those adjustments amount to,
  rather than gathering the numbers already on screen, and shall write the
  tables of FR-091 and the page of FR-092 for that run together with the
  configuration document that produced it. Running that document on the command
  line shall give the same answer (NR-013). Confirming adds an answer; it does
  not erase the one the procedure reached, which shall stay readable and
  downloadable.

  Two things follow and are requirements, not conveniences. Re-running is what
  makes the tables honest: a table of combinations tried, assembled from an
  adjusted answer, would describe the search that produced the answer being
  overridden. And every adjustment the page offers shall be expressible in a
  configuration document, so that FR-107 continues to hold — a coupling the
  command line cannot be asked for is a coupling the page may not offer.
- **FR-108** A page whose server does not answer shall say so as a state of
  its own, naming the address it is holding and what the reader should do, and
  shall return to work by itself once the server answers again. It shall never
  report the unreachable server as a fault in the reader's measurements.

---

## 5. Numerical requirements

The page adds no computation of its own. One requirement binds the answer it
hands back.

- **NR-013** The confirmed answer of FR-112 and the answer the command line
  gives for the configuration document downloaded with it shall agree on every
  carrier density, every mobility and every residual to `1e-9` relative.
  Timings and the table of combinations tried are properties of a search rather
  than of an answer, and are excluded by name.

---

## 6. Physical model contract

Unchanged.

---

## 7. Acceptance criteria

| ID | Criterion | Default |
| --- | --- | --- |
| AC-033 | Longest wait, in seconds, between a stop request and the job reporting stopped: the budget of the fit that is running and a margin | `AC-029 + 5` under the data rule; the peaks rule's own budget `+ 5` |
| AC-034 | Rows of each file shown before the mapping is confirmed | `8` |
| AC-035 | Longest wait, in seconds, between the server answering again and the page leaving the state of FR-108 | `3` |
| AC-036 | Carriers a reader may pin at one temperature under FR-109, holes and electrons together | `8` |
| AC-037 | Coupling strengths offered for a band under FR-109, weak, normal and strong | `1e-5`, `1e-4`, `1e-3` |
| AC-038 | Temperatures a band needs before a second-order coupling can act | `3` |
| AC-039 | Longest a coupled refit of a band may run before it is abandoned, in seconds | `1800` |
| AC-040 | Starting points for a coupled refit of a band | `1` |
| AC-041 | Longest a refit at a count the reader pinned may run at one sweep, in seconds | `1800` |
| AC-042 | Starting points for a refit at a count the reader pinned | `4` |

---

## 8. Out of scope

- **More than one user.** The server is bound to the loopback interface and
  holds jobs in memory; a second person on the network cannot reach it, and a
  restart forgets every job. Both are deliberate (plan 001 section 6.1).
- **Remembering analyses between runs.** The reader downloads what they want to
  keep.
- **Editing the carrier set on the page.** Holding a count fixed (FR-090) and
  every other setting of the configuration document stay reachable by supplying
  a document (FR-102); a form for each would be a second, weaker editor for the
  same document.
- **A settings editor on the adjustment step.** The step of FR-112 holds the
  carrier count, the band and the coupling, and nothing else. Every other
  setting stays in the configuration document (FR-102). Without this sentence
  the step grows one form per setting and the paragraph above it becomes a dead
  letter.
- **Installers, code signing and automatic updates.** The folder is zipped and
  sent.

---

## 9. Deliberately left out of this version

- **A fixed port.** A fixed port is a guess about a machine nobody has seen.
- **A single-file executable.** Measured in the sibling project: slower to start
  by more than a factor of two and shaped like a dropper to antivirus heuristics
  (plan 001 section 6.1).
