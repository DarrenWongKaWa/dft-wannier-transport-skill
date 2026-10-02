# Paper numbers: every quoted number recomputed and asserted

Sources: the manuscript project (its handoff notes, a manuscript-number audit script, a shared helper module for
material data, the figure scripts) and the computation project's paper handoff notes and methods record.

## N1. An audit script recomputes every quoted number and asserts the text

- For each claim: (exact string as it appears in the .tex, value recomputed from the data files, significant digits,
  quoted value). Pass only if (i) the recomputed value rounds to the quoted value and (ii) the string is present in the
  flattened text (whitespace collapsed, abstract + all section files).
- Methods statements: pairs (string in the manuscript, string that must occur in the package's methods record), e.g.
  ("a 520~eV cutoff", "ENCUT 520 eV"). Facts thereby trace to a file:line citation.
- Exit status 1 on any mismatch; run after every text or data change, before every build.
- Scale reached: 167 numbers + 35 methods statements (round 6); 105 + 18 (round 5); 86 (round 4).
- Matching rules must be explicit: rounding to N significant digits; one-sided bounds ("<", value); order of
  magnitude; tuples (lower, upper) for ranges written as "lo--hi" in the text.

## N2. Negative controls

- Plant errors (a wrong digit in the text, a wrong value in a data file, a missing methods string) and confirm the audit
  fails on each (round 6: 3 planted errors, all caught; theory suite: 6/6 negative controls). An audit that has never
  failed proves nothing.

## N3. Snapshot before editing; equations untouchable

- Copy the whole manuscript tree to the manuscript folder's `archive/before_<round>_<date>/` before a round of edits (89 files for round 6).
- Equations were verified once (28/28 numerical checks + 6/6 negative controls) and are ported verbatim; never
  "improve" a formula while editing prose. If a formula must change, re-run the verification suite.
- After the build, check that existing labels keep their numbers (125 labels in round 6) and that there are 0
  undefined references.

## N4. Data come from the released bundle, never from working directories

- Paper scripts read an unpacked copy of the final deliverable zip after checking its sha256, plus the package inputs
  through an environment variable that points to the package root. Shared helpers live in one module.
- **Top risk**: after a model change, paper scripts still read superseded data. On 2026-10-02 three scripts (dataset
  and record builders) still read the old hBN model or old records. After every model or package change: grep all
  scripts for data paths and list them with "reads / problem / change to" (a table in the paper handoff notes).

## N5. After a model change, re-check the narrative sentence by sentence

- A model change can flip signs and change magnitudes by more than an order of magnitude; every ratio the narrative
  uses can move. Mechanistic explanations built on the old numbers can become false.
- Produce a table: location, old statement, new statement, source record (a section of the paper handoff notes).
  Separate "still valid" from "must change" from "needs rethinking".

## N6. Do not generalise from one filling, one strain, one material

- An early scaling claim made from a single filling did not survive scans at further fillings and was withdrawn.
- Rule: before writing a scaling statement, vary the control parameter (filling, strain) at least three times.

## N7. Conventions surfaced by recomputation

- Recomputing from raw data exposes definition differences that copied tables hide:
  - Delta_FS on the Fermi contour (the paper's definition) vs minimum over a 2 meV shell (the package tool) differed by
    3-5 %, and anything derived from Delta_FS moved by the same amount (conventions_and_units.md C7);
  - two discretisations of the cyclotron mass dA/dE differed by 0.2 % (a 750^2 grid over a valley box of half-width
    0.012 with a +-2 meV central difference vs the pocket tool's 1600^2-cell box of half-width 0.02;
    conventions_and_units.md C5): pick one, state it;
  - a functional-form claim handed over in notes was not supported once recomputed from the data.
- Record each difference in the package notes (the run notes) without silently changing either side.

## N8. Methods information with citations and explicit unknowns

- One methods file where every statement cites `file:line`; derived numbers marked `[derived]`; missing provenance
  written as **UNKNOWN**, never guessed (MoS2 strain coefficients, early AI tools, cluster name).
- A "missing information" list at the end: what the author must supply vs what stays unknown without affecting the
  conclusions.
- AI-use statement written from records: which steps were done by which tool (commit trailers, session logs), and
  that no calculation was repeated by hand when that is the case.

## N9. Literature and normalisation

- Check a normalisation against at least one published formula: in the example the project's normalisation was 1/2 of
  one published formula read literally and equal to another (verified); record which one is matched and how.
- Verify bibliography metadata (Crossref); mark unverified entries `% VERIFY`.

## N10. Multi-session manuscript work

- A HANDOFF.md with a STATUS line, numbered rounds of checkbox items, "ground truth that must not be re-litigated",
  and a log. A `.session_lock` with a unix time: if < 90 min old, another session is active, do nothing; otherwise
  write the time, work, refresh it.
- Edit the manuscript only when asked; no git commits there.

## N11. Certificates belong to a manuscript snapshot

- **Symptom**: a package that independently re-derived the manuscript's equations certified the displays of one manuscript version while the manuscript moved
  on (three blocks reformatted, one display removed, one added, renumbering in an appendix).
- **Check/fix**: never re-pin hashes or copy PASS verdicts onto new text. Freeze the new version, map it display by
  display onto the certified targets (identical / formatting only / changed / removed / new), and state the coverage;
  rerun the certification (here Wolfram) only for changed or new targets. Mark material-specific relations as out of
  scope rather than giving them an "exact" scope.
- **Source**: the replay package's version-mapping script and version map.

## N12. Recompute claims from the handoff before writing them

- A handoff note made a claim about the functional form of a response that the recomputed data did not support, and a
  Fermi-surface scale taken from the package (a 2 meV shell minimum) was 5 % below the contour value the text defines. Recompute every handed-over
  number from the data with the paper's own definitions.
- **Source**: the project's run notes.

## Before you report a number (checklist)

- [ ] It comes from a filed record (RUN.json), converged N/N boxes, worst err/target <= 1.
- [ ] Cross-checked: anchor point, independent integral or known limit (clean-limit BCD check), symmetry zero.
- [ ] Model uncertainty stated where relevant (manifold ~2 %, symmetry residual ~2 %).
- [ ] Units and sign conventions stated (q = -e, single 1/2, sheet units), definitions of E_F, Fermi-surface scales
      and crossover scales.
- [ ] Scope stated (strain, filling, temperature); extrapolations labelled.
- [ ] Recomputed by the audit script from the released data; string asserted in the text; negative control done.
- [ ] Provenance traceable: record id, package version and sha256, script.
