# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project overview

NYC TLC trip data warehouse: ingest raw yellow taxi and high-volume FHV (rideshare) trip records from the [TLC trip record data portal](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), land them in GCS and BigQuery, then transform with dbt.

**Stack:** Python 3.12, [uv](https://docs.astral.sh/uv/), dbt (BigQuery adapter), Google Cloud Storage, BigQuery.

## Repository layout

```
python-scripts/     # ETL and GCP utility scripts
  get_data.py       # Main pipeline: download → GCS → BigQuery
dbt/
  models/staging/   # Staging models (stg_*) and source/schema YAML
  seeds/            # Lookup CSVs (vendor, rate_code, payment_type, hvfhs_license)
```

Field definitions for raw TLC data are documented in `README.md`.

## Setup

```bash
# Install dependencies (uses uv.lock)
uv sync

# Configure environment (copy and fill in values)
cp .env.example .env
```

Required environment variables:

| Variable | Purpose |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON |
| `GCS_BUCKET` | Target GCS bucket for raw files |
| `BQ_DATASET` | BigQuery dataset for raw tables (e.g. `nyc_taxi_data`) |

dbt uses a `default` profile targeting BigQuery. Configure `~/.dbt/profiles.yml` separately — it is not checked into this repo.

## Common commands

```bash
# Run the full ETL pipeline (download 2020 data, upload to GCS, load to BQ)
uv run python python-scripts/get_data.py

# dbt (run from dbt/ directory)
cd dbt
uv run dbt seed
uv run dbt run
uv run dbt test
uv run dbt build          # seeds + run + test

# Docker (ETL only)
docker build -t nyc-taxi-warehouse .
docker run --env-file .env nyc-taxi-warehouse
```

## Architecture

```
TLC parquet/CSV  →  python-scripts/get_data.py  →  GCS (raw/)  →  BigQuery raw tables
                                                                          ↓
                                                              dbt staging models (views)
                                                                          ↓
                                                              seeds (lookup dimensions)
```

**Raw BigQuery tables** (loaded by `get_data.py`):

- `yellow_trips`, `rideshare_trips`, `taxi_zone_lookup`

**dbt sources** are declared in `dbt/models/staging/_sources.yml` under source name `raw`, schema `nyc_taxi_data`.

## Coding conventions

### Python (`python-scripts/`)

- Python 3.12+, managed with uv (`pyproject.toml` + `uv.lock`).
- Use single quotes for strings.
- Load `.env` from the repo root via `Path(__file__).parent.parent / '.env'`; skip when running in Docker (no `.env` file).
- Use `pathlib.Path` for file paths.
- GCP clients: `google.cloud.storage`, `google.cloud.bigquery`.
- HTTP downloads: `httpx`.
- Keep scripts focused; `get_data.py` is the production ETL entry point. Other scripts (`gcp_testing.py`, `bq_load_testing.py`) are dev utilities.

### dbt (`dbt/`)

- Project name: `nyc_taxi_warehouse`. Staging models materialize as **views** (see `dbt_project.yml`).
- Follow the existing CTE pattern: `source` → `renamed` → final `select`.
- Column naming: **snake_case**. Cast types explicitly (`int64`, `numeric`, `timestamp`, `string`).
- TLC `Y`/`N` flag columns → boolean via `case when 'Y' then true when 'N' then false else null end`.
- Financial columns: suffix with `_amount` (e.g. `fare_amount`, `tolls_amount`).
- Datetime columns: suffix with `_datetime`; derive `pickup_date` as `cast(pickup_datetime as date)`.
- Filter out rows with null pickup/dropoff timestamps in staging models.
- Document models and key columns in `_staging.yml`; add `not_null` tests on required fields.
- Declare raw tables in `_sources.yml`; do not hardcode schema/table names outside of source macros.
- Seeds are small lookup CSVs with a header row and snake_case column names.

### General

- Minimize scope — match existing patterns before introducing new abstractions.
- Do not commit secrets, credentials, or generated data files.
- Do not create git commits unless explicitly asked.

## Do not modify

- `uv.lock` — only update via `uv lock` / `uv sync` when dependencies change.
- `target/`, `dbt_packages/`, `logs/` — dbt generated output.
- `*.parquet` — downloaded/generated data (gitignored).
- `.env` — local secrets (gitignored).

## Verification

After making changes, run the relevant checks:

| Change type | Verify with |
|---|---|
| Python scripts | `uv run python python-scripts/<script>.py` (or dry-run logic review if GCP creds unavailable) |
| dbt models | `cd dbt && uv run dbt compile && uv run dbt run --select <model> && uv run dbt test --select <model>` |
| Seeds | `cd dbt && uv run dbt seed && uv run dbt test` |
| Dependencies | `uv sync` succeeds without lockfile conflicts |

If GCP credentials are not available, at minimum ensure SQL compiles (`dbt compile`) and Python syntax is valid.

## Adding new work

- **New raw data source:** extend `get_data.py` (or a new script following its patterns), add a source in `_sources.yml`, then create a `stg_*` model.
- **New dbt layer (intermediate/mart):** add a subdirectory under `dbt/models/`, configure materialization in `dbt_project.yml`, and follow existing naming conventions.
- **New lookup data:** add a CSV to `dbt/seeds/` and reference it from staging or mart models.
