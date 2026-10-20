# parser/

Turns grade-report PDFs into one Parquet file per term (`data/parquet/<term>.parquet`).

- `parse_grades.py`: PDF -> rows
- `run_parse.py`: parallel over terms (`multiprocessing`), hash-based skip
- `tests/fixtures/`: a few extracted PDF pages with hand-checked expected rows

pdfplumber is the default. Benchmark PyMuPDF if speed matters.

## Report layout (stable 1999 → 2025)

Each page has a header (term, college, department name, subject code + abbreviation), then one line per section:

```
<course name?> <course #> <section> <# grades> <avg GPA | *** | .> A AB B BC C D F S U CR N P I NW NR Other
```

## Quirks

**Add a test whenever you touch one of these.**

| Quirk | Handling |
|---|---|
| Course name appears only on the first section line, or only on the `Course Total` line for multi-section courses | Fill the name backward onto pending sections of the same course number |
| `***` instead of GPA/percentages (sections with ≤5 students) | Keep the row, set `redacted = true`, leave grade columns null |
| `.` in a percentage column | Means 0.0 |
| `Course Total`, `Dept. Total`, `Summary by Level` rows | Not sections. Use Course Total only for its name; skip the others |
| Subject code/abbreviation is in the page header, not the row | Carry it down to every row on the page |
| Long department names are truncated in the header | Use subject code as the key, never the long name |
| Cross-listed courses appear once per subject, **not combined** | Deduplicate in dbt (`int_` layer), not here |
| Law School non-standard grades are excluded from the report | Nothing to parse; noted in docs |
| COVID terms label S and U columns `S/SD` and `U/UD` | Parse grade columns **by position, never by header text**; map both to `s` and `u` |
| Last page has a university-wide `Total <n> <gpa> ...` line | Parse it and store it as the term's expected total for reconciliation |
| Section numbers have leading zeros (`001`) | Always text. Never let pandas infer them as ints |
| From term 1194, some titles contain `�` that extracts as spaces | Normalize titles; match courses on `(subject_code, course_number)`, never title |

## Known open issues

- **Percentage-sum failures:** about 1.6–1.9% of graded sections don't sum to 100 ± 1 (77 in `1262`, 79 in `1214`). This is likely a column misread on wrapped lines. Fix it in the parser; the dbt test stays strict.
- **Reconciliation gap:** `1214` captures 99.6% of the report's grand total (about 650 grades missing). Target is ≥99.9% on every term.

See `docs/data-source.md` for prototype numbers.
