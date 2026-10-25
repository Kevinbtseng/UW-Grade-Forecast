# dbt/

All cleaning and feature engineering happens in SQL models with tests. Conventions: lowercase keywords, CTEs over subqueries, one model per file, prefixes `stg_` / `int_` / `fct_` / `dim_`.

## Source: `raw.grade_sections`

One row per section line, exactly as parsed:

`term int, subject_code text, subject_abbr text, course_number int, section text, course_name text, num_grades int, avg_gpa numeric null, redacted bool, a, ab, b, bc, c, d, f, s, u, cr, n, p, i, nw, nr, other numeric null`, plus provenance columns (`source_file`, `source_sha256`, `parser_version`, `loaded_at`).

## Layers

**staging (`stg_grade_sections`)**
- Cast types and left-pad `section` to 3 characters.
- Normalize titles (collapse whitespace; fix known `�` cases).
- Derive `term_year`, `term_season`, and `course_level` (100s/200s/…).

**intermediate**
- `int_sections_deduped`: collapse cross-listed duplicates. These share the same term, course name, num_grades and identical grade percentages under different subjects. Keep a canonical subject plus a `crosslisted_subjects` array.
- `int_letter_grade_sections`: non-redacted sections with ≥1 letter grade. Computes the **letter-only A share**.

**marts**
- `dim_course`: one row per `(subject_code, course_number)` with latest title, level, and first/last term seen.
- `fct_section_grades`: cleaned section-level facts.
- `fct_course_term`: course × term aggregates (students, GPA weighted by num_grades, A share, section count).
- `course_term_features`: one row per course × term with **only features known before that term starts** (see `ml/CLAUDE.md`).

## Tests (minimum)

- `unique` on `(term, subject_code, course_number, section)` in staging.
- `not_null` on keys.
- `avg_gpa` between 0 and 4.
- Grade percentages sum to 100 ± 1 for non-redacted rows, **except Law School (subject `528`)**. The report excludes Law's non-standard grades, so its percentages sum to under 100 in the source PDF. This is the only exemption; don't widen it. In `1262`, 5 non-Law sections (subjects `272`, `310`, `745`) also sum to under 100 and need a look before the test can pass.
- `a_share` between 0 and 1.
- Row counts per term within an expected range (catches a silently broken parse).
- **Reconciliation:** the sum of `num_grades` per term (non-total rows) is within 1% of the report's grand total. This is the main parser-accuracy check.
