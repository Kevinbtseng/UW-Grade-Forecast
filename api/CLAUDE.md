# api/

Read-only FastAPI service. Pydantic + SQLAlchemy (or psycopg).

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | status |
| GET | `/courses?query=` | search by subject abbreviation, number, or title (limit 20) |
| GET | `/courses/{subject_code}/{course_number}` | course info + history (GPA, A share, students per term) |
| GET | `/courses/{subject_code}/{course_number}/prediction` | next-term predictions + error band + model version |
| GET | `/meta` | data coverage (first/last term), model metrics summary |

## Rules

- Pydantic response models for everything; OpenAPI docs at `/docs`. The frontend generates its types from this schema, so keep it accurate.
- Never load a model file. Read predictions from `ml.predictions`.
- No raw DIR data and no instructor fields, ever.
- CORS: allow the Vite dev origin locally; lock it down for any deploy.
- Tests use `httpx`/`TestClient` against a seeded test database.
