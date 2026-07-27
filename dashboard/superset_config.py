"""Superset runtime configuration.

Values are read from environment variables (see .env). This file is mounted
into the container at /app/superset_config.py and pointed to by
SUPERSET_CONFIG_PATH.
"""

import os

# --- Core -------------------------------------------------------------------
SECRET_KEY = os.environ["SECRET_KEY"]

# Metadata database (Postgres) — stores dashboards, charts, users, etc.
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{os.environ.get('POSTGRES_USER', 'superset')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'superset')}@"
    f"superset-db:5432/{os.environ.get('POSTGRES_DB', 'superset')}"
)

# --- Behaviour --------------------------------------------------------------
# Allow Superset to run ad-hoc queries against connected databases (DuckDB).
FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "EMBEDDED_SUPERSET": True,
}

# DuckDB is single-process; keep the SQLAlchemy pool small to avoid lock churn.
SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

# Optional: allow CSV/file uploads to be disabled in a portfolio context.
ROW_LIMIT = 50000
