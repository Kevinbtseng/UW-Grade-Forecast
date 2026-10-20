# Roadmap

## Phase 0: Setup
- [ ] Repo scaffold, Docker Compose with Postgres, Makefile, `.env.example`, pytest config.

## Phase 1: Parse
- [ ] Write `parser/parse_grades.py` from the quirks table in `parser/CLAUDE.md`. The earlier prototype is not in this repo; its numbers in `docs/data-source.md` are targets to check against.
- [ ] Fix the 77 percentage-sum rows in 1262 (likely wrapped/misaligned lines).
- [ ] Fixtures + tests for every quirk in `parser/CLAUDE.md`.
- [ ] Run across all terms in parallel. Benchmark pdfplumber vs. PyMuPDF and record total runtime.
- [ ] Spot-check old (972–1004), middle (~1162), COVID (1214) and new (1262) terms by hand.
- [ ] Parse each report's grand-total line and reach ≥99.9% reconciliation on every term.

## Phase 2: Load + dbt
- [ ] `COPY` loader with per-term idempotency and provenance columns.
- [ ] Staging, intermediate (cross-list dedupe, letter-only A share) and marts.
- [ ] All tests in `dbt/CLAUDE.md` passing; `dbt docs generate` lineage screenshot for the README.

## Phase 3: ML
- [ ] `course_term_features` with leakage test.
- [ ] Baselines, then Ridge / RF / HGB for both targets.
- [ ] Time-based validation, final test evaluation, `metrics.json`.
- [ ] Short write-up of results (what helped, where the model fails).

## Phase 4: API
- [ ] Endpoints, Pydantic models, tests, CORS.
- [ ] Batch predictions table populated by `make predict`.

## Phase 5: Frontend
- [ ] Vite + TS scaffold, search page, course page with charts and prediction cards.
- [ ] Generated API types; loading, empty and error states.

## Phase 6: Extensions (optional, after Phases 1–5 ship)
- [ ] DIR features (section size, meeting time, days) via the Madgrades extractor as an external Docker tool, respecting the DIR constraints.
- [ ] Deploy (AWS: RDS + ECS/App Runner for the API, S3 + CloudFront for the frontend) with Terraform.
- [ ] Prediction intervals (quantile regression with `HistGradientBoostingRegressor(loss="quantile")`).

# Resume metrics

Fill these in from real runs. Never estimate.

- Rows parsed: [X] sections across [Y] terms ([Z] PDF pages); parse runtime [T] (and speedup from parallelism).
- Load time for the full dataset with `COPY`: [T].
- dbt: [N] models, [M] tests; data-quality issues caught: [K].
- Model results: GPA MAE [a] vs baseline [b] ([p]% better); A-share MAE [c] vs baseline [d] ([q]% better).
- API p95 latency for the course endpoint: [L] ms (optional, if load-tested).

# Open questions

- Final project name.
- Minimum letter-grade threshold for a modeled course-term (start at 20 and tune).
- How to treat COVID-era terms `1204` and `1214` (flag vs. exclude). Check `1212` (Fall 2020-2021) for the same S/SD signal.
- Whether to include summer terms (not in the archive's grade reports; probably skip).
- Canonical subject for cross-listed courses (lowest subject code, or most students).
