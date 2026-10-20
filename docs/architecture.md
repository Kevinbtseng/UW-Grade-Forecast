# Architecture

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | Single language for parser, load, ML, API |
| PDF parsing | pdfplumber | Try PyMuPDF if speed matters. Parallelize across terms with `multiprocessing` |
| Intermediate files | Parquet (pyarrow) | Typed, compressed; lets the DB be rebuilt without re-parsing |
| Database | PostgreSQL 16 | Schemas: `raw`, `staging`, `intermediate`, `marts`, `ml` |
| Load | `COPY` via psycopg | Never row-by-row inserts |
| Transform | dbt-core + dbt-postgres | All cleaning and features in SQL models with tests |
| ML | pandas, scikit-learn, joblib | `metrics.json` per run |
| API | FastAPI + Pydantic + SQLAlchemy (or psycopg) | Read-only; CORS enabled for the frontend |
| Frontend | React + TypeScript + Vite, TanStack Query, Recharts | Search page plus course page |
| Infra | Docker Compose, Makefile | One command to run everything locally |
| CI | GitHub Actions | pytest, dbt build, smoke-train, frontend lint/build |
| Quality | pytest, ruff, mypy (light), ESLint | |

## Deliberately excluded

- **Airflow:** new data arrives twice a year, so a Makefile plus a manual GitHub Actions workflow is enough.
- **Streamlit:** replaced by React, which builds skills for the next project.
- **DuckDB/warehouse:** the data fits easily in Postgres.
- **MLflow:** overkill for two models.

## Repository layout

```
.
├── CLAUDE.md
├── README.md
├── Makefile
├── docker-compose.yml          # postgres, api, frontend
├── .github/workflows/
│   ├── ci.yml                  # on push/PR
│   └── ingest.yml              # workflow_dispatch: add a new term
├── data/                       # gitignored
│   ├── pdfs/
│   └── parquet/                # <term>.parquet
├── docs/
├── parser/                     # parse_grades.py, run_parse.py, tests/
├── loader/                     # load.py: Parquet -> raw.grade_sections via COPY
├── dbt/                        # models/{staging,intermediate,marts}, tests/
├── ml/                         # features, train, predict, evaluate, artifacts/
├── api/                        # main.py, routers/, tests/
└── frontend/                   # src/, package.json
```

## CI (GitHub Actions)

`ci.yml` (push and PR):
1. `ruff` + `pytest` for parser/loader/ml/api. Parser tests run on small PDF-page fixtures with hand-checked expected rows.
2. Spin up a Postgres service container, load a small fixture dataset, then run `dbt build`.
3. Smoke-train on the fixture data, asserting that the pipeline runs and `metrics.json` is produced. Metric values aren't asserted.
4. Frontend: `npm ci`, `tsc --noEmit`, ESLint, `vite build`.

`ingest.yml` (`workflow_dispatch`, input: term code): parse → load → dbt → train → predict for a newly published term. Used twice a year.
