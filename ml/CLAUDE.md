# ml/

- `features.py`: reads `marts.course_term_features`
- `train.py`: trains the GPA and A-share models
- `predict.py`: writes `ml.predictions`
- `evaluate.py`: compares baselines vs models and writes `metrics.json`
- `artifacts/`: models are gitignored; `metrics.json` is committed so results are reviewable in PRs

Tools: pandas, scikit-learn, joblib. No MLflow.

## Targets (two separate models, same features)

1. **`avg_gpa`:** course-level GPA for the term, weighted by `num_grades` across sections.
2. **`a_share`:** **letter-grade-only** share of A's, `A / (A + AB + B + BC + C + D + F)` after converting percentages back to counts.
   - Don't use the report's raw A% directly. Its denominator includes S/U/CR/N/P/I/NW/NR/Other.

## Unit and scope

- Predict at the **course × term** level, not the section level.
- Exclude redacted sections, pass/fail-only courses, and course-terms with fewer than N total letter grades (start at 20; tune).

## Features (strictly from prior terms)

- **History:** last-offered GPA and A share, rolling 3-offering mean, trend (slope over the last k offerings), number of prior offerings, terms since last offered.
- **Subject:** subject-level mean GPA and A share over the prior 2 years.
- **Course:** level (100–900), fall vs. spring.
- **Size:** prior-offering enrollment and section count.
- **Optional:** term-wide average to capture grade inflation.
- **Missing history:** leave as NaN. `HistGradientBoostingRegressor` handles NaN natively; impute for Ridge.
- "Last offering" means the previous term **in which the course was actually offered**, not `term - 10`. Many courses skip terms.
- **Keep a test that asserts no feature for term T uses data from terms ≥ T.**

## Splits (by time, never random)

- **Train:** terms ≤ `1224` (Spring 2021-2022).
- **Validate:** `1232`–`1244` (academic years 2022-2023 and 2023-2024). Use for tuning and model selection.
- **Test:** `1252`–`1264` (academic years 2024-2025 and 2025-2026). **Touch it once, at the end.**
- **Tuning:** `TimeSeriesSplit`-style expanding windows.
- **COVID terms:** `1204` and `1214` used S/U "disrupted" grading (1214's S share is about 6x normal). Add an `is_covid_term` flag, test training both with and without these terms, and document the choice. Check `1212` for the same signal.

## Models

1. **Baselines:** last offering's value, and the rolling 3-offering mean.
2. `Ridge` (`Pipeline` with `SimpleImputer` + `StandardScaler`).
3. `RandomForestRegressor`.
4. `HistGradientBoostingRegressor`.

## Metrics

- MAE (primary) and RMSE on the test set, for both targets.
- **% MAE improvement over baseline**, the headline number.
- MAE broken down by course level and by prior-offering count. The model should help most where history is short.
- Write everything to `ml/artifacts/metrics.json`.

## Inference

- **Batch only.** `make predict` writes `ml.predictions(subject_code, course_number, target_term, pred_avg_gpa, pred_a_share, model_version, created_at)`.
- Include a typical-error band (validation MAE) so the UI can show uncertainty.
