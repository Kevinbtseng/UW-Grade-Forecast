# Data source

## Where the PDFs come from

- **Source:** `https://github.com/Madgrades/madgrades-pdf-archive`, `grades/` folder. There is one "Percentage Distribution of Grades" report per term, named `<termcode>-grades.pdf`.
- **Coverage (checked Oct 2026):** term `972` (Fall 1996-1997) through `1264` (Spring 2025-2026), fall and spring only. About 59 files, roughly 230 MB for the repo.
- **Term `1214` (Spring 2020-2021) is missing from the archive** (both `grades/` and `dir/`). The registrar publishes it on Box (`report-gradedistribution-2020-2021spring.pdf`, 454 pages). Download it manually and save it as `data/pdfs/1214-grades.pdf`. With it, coverage is complete for every fall and spring term from `972` to `1264`. Consider contributing it to the archive by PR.
- The registrar's Box links contain the same PDFs, but Box needs JavaScript, so don't automate it. Clone the archive instead.
- Summer terms are not in the archive's grade reports.

## Legal and usage notes

- **`madgrades-extractor` (Java) is not used.** It has no license, and grade reports are simple enough to parse in Python. If DIR features are added later, run the extractor as an external tool (Docker, pinned commit), never vendor its code, and credit it in the README.
- **DIR (Departmental Instructional Report) data:** UW–Madison does not endorse republishing it externally. If used, keep DIR files and DIR-derived raw tables out of git and public deploys. Expose only predictions and course-level aggregates, and don't build features that rank or target individual instructors.
- Grade reports are public records, but keep raw PDFs and Parquet out of the repo and link to the archive instead.
- Law School non-standard grades are excluded from the reports.
- Credit Madgrades and the UW Registrar in the README.

## Prototype results (snapshot, Oct 2026)

These numbers come from the prototype parser. They will go stale as the parser improves; update or remove them when they do.

### Fall 2025-2026 (`1262`)
- 481 pages → **10,445 section rows**, 175 subjects, **214,067 grades**. Took about 2 min with pdfplumber (single process).
- **49.2% of sections are redacted**, but they hold only **9,870 grades (~4.6%)**. Dropping them for modeling loses little.
- **77 of 4,922 graded sections** had percentages not summing to 100 ± 1 (open parser bug).

### Spring 2020-2021 (`1214`)
- Parsed with **no parser changes**: **9,675 sections**, 176 subjects, **174,843 grades**. 52.9% of sections are redacted.
- **79 of 4,167** graded sections fail the 100 ± 1 sum check (same bug).
- **Reconciliation:** the report's grand total is 175,500 grades, so the parser captured **99.6%** (about 650 missing).
- **COVID signal:** mean S% per section is **5.96%**, vs 0.91% in `1262`.
