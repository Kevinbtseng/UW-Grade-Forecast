# CLAUDE.md

Guidance for Claude (and humans) working in this repository. Read this before making changes.

## Project

**UW Grade Forecast** (working name). This project parses UW–Madison's public grade-distribution PDFs into PostgreSQL. It forecasts each course's **average GPA** and **share of A's** for upcoming terms and serves them through a read-only FastAPI backend and a small React + TypeScript frontend.

The prediction is the product. The headline result is how much the models beat a naive "same as last time" baseline on held-out future terms. Re-creating madgrades.com is not the goal.

```
PDF archive ─► parse (pdfplumber) ─► Parquet per term ─► COPY ─► Postgres raw
   ─► dbt staging ─► intermediate ─► marts ─► train ─► predict (batch)
   ─► ml.predictions ─► FastAPI (read-only) ─► React UI
```

**Stack:** Python 3.12, pdfplumber, Parquet (pyarrow), PostgreSQL 16 (schemas `raw`, `staging`, `intermediate`, `marts`, `ml`), dbt-core, scikit-learn, FastAPI, React + TS + Vite, Docker Compose, Makefile, GitHub Actions.

## Where to find details

| Topic | File |
|---|---|
| Parser rules and PDF quirks | `parser/CLAUDE.md` |
| Data model, dbt layers, dbt tests | `dbt/CLAUDE.md` |
| ML targets, features, splits, metrics | `ml/CLAUDE.md` |
| API endpoints and rules | `api/CLAUDE.md` |
| Frontend pages and rules | `frontend/CLAUDE.md` |
| Data source, coverage, legal notes, reference results | `docs/data-source.md` |
| Stack rationale, repo layout, CI | `docs/architecture.md` |
| Roadmap, resume metrics, open questions | `docs/roadmap.md` |

## Commands

```bash
make db        # start Postgres
make pdfs      # clone/update the PDF archive into data/pdfs/
make parse     # PDFs -> data/parquet/<term>.parquet (parallel, skips unchanged)
make load      # Parquet -> raw.grade_sections (idempotent per term)
make dbt       # dbt build (models + tests)
make train     # train both models, write ml/artifacts/ + metrics.json
make predict   # write next-term predictions to ml.predictions
make api       # FastAPI on :8000
make web       # React dev server on :5173
make all       # parse -> load -> dbt -> train -> predict
make test      # pytest + dbt test + frontend lint/typecheck
```

## Term codes

- Format: `1` + academic-year end (last two digits) + term digit (`2` = Fall, `4` = Spring, `6` = Summer).
- The registrar labels terms by **academic year**. For example, `1262` = "Fall 2025-2026" and `1264` = "Spring 2025-2026".
- **Refer to terms by code or academic-year label, never "Spring 2021"-style names.** Calendar names are ambiguous.
- Old codes drop the leading `1` and have three digits (`972` = "Fall 1996-1997").
- Store, sort and compare terms as `int`, never text.

## Conventions

- **Keys:** a course is `(subject_code, course_number)`. A section adds `term` + `section`. **Never join or match on titles.**
- **Types:** `term` is int, `section` is text (leading zeros, e.g. `001`), percentages are numeric 0–100, shares are 0–1.
- **No leakage:** a feature for term T may only use data from terms < T.
- **Data-quality tests:** when a test fails, fix the parser or model. Don't loosen the test.
- **Python:** type hints on public functions, no bare `except`. Use `logging` (not `print`) except in a script's final summary.
- **SQL (dbt):** lowercase keywords, CTEs over subqueries, one model per file. Prefix models `stg_`, `int_`, `fct_`, `dim_`.
- **Commits:** `type(scope): description`, imperative mood (`feat(parser): handle wrapped course names`).
- **Secrets:** DB credentials in `.env` (gitignored). Keep `.env.example` current.

## Idempotency

- **Parse:** skip a term if the PDF's SHA-256 and the parser version match the Parquet metadata.
- **Load:** run `DELETE FROM raw.grade_sections WHERE term = :term`, then `COPY`, in one transaction per term. Never insert row by row.
- Every raw row carries `source_file`, `source_sha256`, `parser_version` and `loaded_at`.

## Hard constraints

- Never commit PDFs or Parquet. `data/` is gitignored.
- Don't automate Box downloads. Clone the Madgrades archive instead.
- Never vendor code from `madgrades-extractor` (it has no license). If it's needed later, run it as an external Docker tool.
- DIR data (if ever used) stays out of git and out of public deploys. The API never serves raw DIR rows or instructor-level data. Don't build features that rank or target individual instructors.
- The API never loads model files. It reads `ml.predictions`.
