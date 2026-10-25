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
| Section codes vary by term: `001`, `00A`, `000A`, `1`, `30` | Treat as sections; match 1 to 4 chars of `0-9A-Z` with at least one digit |
| Term `1032` prints `TERM:1032` and `GradesGPA` with no spaces, and repeats the subject header inside the summary block | Header regexes allow zero spaces. Reset summary mode only when the subject code changes |
| Term `1032` prints `#Num!` in the GPA column for sections graded only S/U | Treat as no GPA (`avg_gpa` null); the 16 grade tokens still follow |
| Terms `1064`, `1072`, `1084`, `1094` print `#Name?` spreadsheet errors in the `Grand Total` line | Leave the expected totals unset; reconciliation returns `None` for these terms |
| `Section Total` rows sum a section listed on several lines (e.g. `971 008` twice) | Skip the total, keep the parts. The same `(course, section)` can therefore repeat |
| A section can have no GPA token without being redacted (only S/U/CR/... grades) | Parse the last 16 tokens as grades; GPA is present only if the token before them looks like `d.ddd` |
| From term 1194, some titles contain `�` that extracts as spaces | Normalize titles; match courses on `(subject_code, course_number)`, never title |

## Known open issues

- **Percentage-sum failures:** about 1.6–1.9% of graded sections don't sum to 100 ± 1 (82 in `1262`, 79 in `1214` from the prototype). In `1262` the new parser's text matches the PDF: 77 of the 82 are Law School (`528`), all sum to under 100, and none to over. This is the report omitting Law's non-standard grades, not a misread. Decision: the dbt sum test exempts subject `528`. The parser changes nothing for these rows. The 5 non-Law cases in `1262` (`272`, `310`, `745`) are not yet explained.
- **Reconciliation:** `1262` captures 99.999% of the report's grand total (214,083 of 214,086). `1214` was 99.6% in the prototype and has not been re-run with this parser. Target is ≥99.9% on every term.

The parser is not written yet. See `docs/data-source.md` for reference numbers from an earlier prototype to check it against.
