# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project overview

NYC TLC trip data warehouse focused on **analytics engineering with dbt**. Raw trip records come from the [TLC trip record data portal](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Models are developed locally on **DuckDB**, then run on **Snowflake** when the project needs cloud scale.

**Stack:** Python 3.12, [uv](https://docs.astral.sh/uv/), dbt, DuckDB (local), Snowflake (production/scale).

**Previous direction:** This repo previously targeted GCS + BigQuery. That path was retired in favor of DuckDB local dev → Snowflake. Do not reintroduce BigQuery/GCP patterns unless explicitly requested.

## Repository layout

```
data/
  get_data.py       # Download TLC parquet files into data/<year>/
dbt/
  models/           # staging (stg_*), intermediate (int_*), marts (planned)
  seeds/            # Lookup CSVs (vendor, rate_code, payment_type, hvfhs_license, etc.)
  macros/           # Shared SQL; isolate warehouse-specific logic here
```

Field definitions for raw TLC data are documented in `README.md`.

## Environment strategy

| Target | Adapter | When to use |
|---|---|---|
| `dev` (DuckDB) | `dbt-duckdb` | Local modeling, unit tests, fast feedback |
| `prod` (Snowflake) | `dbt-snowflake` | Full history, sharing, production schedules |

Keep model SQL warehouse-portable. When DuckDB and Snowflake diverge (types, functions, external stages), solve it in macros or thin wrapper models—not duplicated business logic.

Example profile shape (configure in `~/.dbt/profiles.yml`, not committed):

```yaml
nyc_taxi_warehouse:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ../data/local.duckdb
      schema: main
    prod:
      type: snowflake
      account: "<account>"
      user: "<user>"
      role: "<role>"
      database: "<database>"
      warehouse: "<warehouse>"
      schema: "<schema>"
      authenticator: externalbrowser  # or key pair / SSO as appropriate
```

## Setup

```bash
# Install dependencies (once pyproject.toml lists them)
uv sync
```

Secrets and connection details belong in `.env` or `~/.dbt/profiles.yml`. Never commit credentials, keys, or local database files with real data.

## Common commands

```bash
# Data retrieval
uv run python data/get_data.py 2020
uv run python data/get_data.py 2020 --dry-run
uv run python data/get_data.py 2020 --force

# dbt — run from dbt/
cd dbt
uv run dbt debug
uv run dbt seed
uv run dbt run
uv run dbt test
uv run dbt build                    # seeds + run + test

# Switch to Snowflake when validating cloud compatibility
uv run dbt run --target prod
```

## Architecture

```
TLC parquet/CSV  →  data/get_data.py  →  data/<year>/*.parquet  →  DuckDB raw layer
                                                    ↓
                                         dbt staging models (views)
                                                    ↓
                                         intermediate + marts
                                                    ↓
                                         Snowflake (same dbt project, prod target)
```

Ingestion details (download cadence, file layout, raw table naming) are still being defined. Prefer landing raw data as files or raw tables first, then declare dbt `sources` pointing at that layer.

## Coding conventions

### Python (`data/get_data.py`)

- Python 3.12+, managed with uv (`pyproject.toml` + `uv.lock`).
- Use single quotes for strings.
- Load `.env` from the repo root via `Path(__file__).parent.parent / '.env'` when needed.
- Use `pathlib.Path` for file paths.
- HTTP downloads: `httpx` (or `requests` if already in dependencies).
- Keep scripts focused; one clear entry point for TLC downloads and loading into the local raw layer.

### dbt (`dbt/`)

- Project name: `nyc_taxi_warehouse`.
- Layer naming: `stg_*` (staging), `int_*` (intermediate), `fct_*` / `dim_*` or domain-specific names for marts.
- Staging models: materialize as **views** unless profiling shows a table is needed locally.
- Follow the CTE pattern: `source` → `renamed` → final `select`.
- Column naming: **snake_case**. Cast types explicitly.
- TLC `Y`/`N` flag columns → boolean via `case when 'Y' then true when 'N' then false else null end`.
- Financial columns: suffix with `_amount` (e.g. `fare_amount`, `tolls_amount`).
- Datetime columns: suffix with `_datetime`; derive `pickup_date` as `cast(pickup_datetime as date)`.
- Filter out rows with null pickup/dropoff timestamps in staging models.
- Document models and key columns in YAML; add `not_null` tests on required fields.
- Declare raw tables in `_sources.yml`; do not hardcode schema/table names outside source macros.
- Seeds are small lookup CSVs with a header row and snake_case column names.

### DuckDB ↔ Snowflake portability

- Prefer ANSI SQL and dbt macros over adapter-specific functions in model bodies.
- Test critical models with `dbt run --target prod` before treating Snowflake as done.
- DuckDB can read parquet directly; Snowflake may use stages or loaded tables—keep that difference in the ingestion layer and sources, not in mart logic.

### General

- Minimize scope — match existing patterns before introducing new abstractions.
- Do not commit secrets, credentials, or generated data files.
- Do not create git commits unless explicitly asked.

## Do not modify

- `uv.lock` — only update via `uv lock` / `uv sync` when dependencies change.
- `target/`, `dbt_packages/`, `logs/` — dbt generated output.
- `data/<year>/`, `*.parquet`, `*.duckdb` — downloaded/generated data (gitignored; `data/get_data.py` is tracked).
- `.env` — local secrets (gitignored).

## Verification

After making changes, run the relevant checks:

| Change type | Verify with |
|---|---|
| Data download | `uv run python data/get_data.py <year>` |
| dbt models (local) | `cd dbt && uv run dbt compile && uv run dbt run --select <model> && uv run dbt test --select <model>` |
| dbt models (Snowflake) | `cd dbt && uv run dbt run --target prod --select <model>` |
| Seeds | `cd dbt && uv run dbt seed && uv run dbt test` |
| Dependencies | `uv sync` succeeds without lockfile conflicts |

If Snowflake credentials are unavailable, at minimum ensure SQL compiles on DuckDB (`dbt compile`, `dbt run --target dev`).

## Adding new work

- **New raw dataset from TLC:** extend `data/get_data.py`, land raw data under `data/<year>/`, add a source in `_sources.yml`, then create a `stg_*` model.
- **New dbt layer:** add a subdirectory under `dbt/models/`, configure materialization in `dbt_project.yml`, follow naming conventions above.
- **New lookup data:** add a CSV to `dbt/seeds/` and reference it from staging or mart models.
- **Snowflake-only optimization:** use macros so the DuckDB `dev` target stays runnable for local development.
