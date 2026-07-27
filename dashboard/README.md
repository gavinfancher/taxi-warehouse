# Dashboard — Apache Superset

A Dockerized [Apache Superset](https://superset.apache.org/) instance for exploring
the NYC TLC warehouse, with the local DuckDB database (`../data/db/local.duckdb`)
mounted read-only.

## Layout

```
dashboard/
├── docker-compose.yml             # superset-db (Postgres 18.4), superset-init, superset
├── docker/requirements-local.txt  # extra drivers (duckdb, duckdb-engine, psycopg2)
├── superset_config.py             # runtime config (metadata DB, feature flags)
├── docker-init.sh                 # one-shot: install drivers, db upgrade, create admin
├── register_duckdb.py             # helper: register the DB + all tables as datasets
├── .env.example                   # copy to .env
└── README.md
```

Uses the **stock `apache/superset` image** — the DuckDB/Postgres drivers in
`docker/requirements-local.txt` are installed at container startup by Superset's
`docker-bootstrap.sh` (so the containers run as `root` to write into the image
venv). No custom image build is needed.

The metadata (dashboards/charts/users) lives in a Postgres container; the
analytics data stays in DuckDB.

## Quick start

```bash
cd dashboard
cp .env.example .env   # edit SECRET_KEY + passwords (a .env is already provided)
docker compose up -d   # first start installs drivers from requirements-local.txt
```

Then open http://localhost:8088 and log in with the `ADMIN_USERNAME` /
`ADMIN_PASSWORD` from `.env` (default `admin` / `admin`).

Watch bootstrap progress with:

```bash
docker compose logs -f superset-init   # finishes and exits
docker compose logs -f superset        # the web server
```

## Connecting to DuckDB

> [!IMPORTANT]
> DuckDB allows **only one writer**. Close any process holding the file
> read-write (DataGrip, a running `dbt` build, a notebook) before Superset
> opens it. If a stale `local.duckdb.wal` exists, open the DB once with a
> writer and run `CHECKPOINT;` so the file can be opened read-only.

In Superset: **Settings → Database Connections → + Database → DuckDB**, and use
this SQLAlchemy URI (the file is mounted at `/data/db` inside the container):

```
duckdb:////data/db/local.duckdb?access_mode=read_only
```

`access_mode=read_only` lets Superset read while dbt/other readers are also
attached. Click **Test Connection**, then save.

## Common commands

```bash
docker compose up -d --build   # build + start
docker compose down            # stop (keeps metadata volume)
docker compose down -v         # stop + wipe Superset metadata
docker compose restart superset
docker compose logs -f superset
```

## Notes

- `duckdb` is pinned to **1.5.3** in `docker/requirements-local.txt` to match the
  version that wrote `local.duckdb`. If you rebuild the warehouse with a newer
  DuckDB, bump the pin and recreate (`docker compose up -d --force-recreate`).
- Drivers are reinstalled on every container start (a few seconds). To bake them
  into a custom image instead, replace `requirements-local.txt` with a Dockerfile.
- `SUPERSET_VERSION` in `.env` pins the image tag; change it if that tag is
  unavailable on Docker Hub.
- This setup omits Redis/Celery (no async queries / alerts) to stay minimal for
  local/portfolio use.
