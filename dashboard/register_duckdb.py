"""Register the DuckDB warehouse and its tables in Superset.

Run inside the superset container:
    docker compose exec superset /app/.venv/bin/python /app/register_duckdb.py
"""

from superset.app import create_app

app = create_app()

DB_NAME = "nyc_taxi_duckdb"
DB_URI = "duckdb:////data/db/local.duckdb?access_mode=read_only"
SCHEMA = "main"

with app.app_context():
    from superset import db
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable

    database = db.session.query(Database).filter_by(database_name=DB_NAME).first()
    if database is None:
        database = Database(database_name=DB_NAME, sqlalchemy_uri=DB_URI)
        db.session.add(database)
        db.session.commit()
        print(f"created database '{DB_NAME}' (id={database.id})")
    else:
        database.sqlalchemy_uri = DB_URI
        db.session.commit()
        print(f"database '{DB_NAME}' already exists (id={database.id})")

    with database.get_inspector() as inspector:
        table_names = sorted(inspector.get_table_names(schema=SCHEMA))

    for name in table_names:
        existing = (
            db.session.query(SqlaTable)
            .filter_by(table_name=name, schema=SCHEMA, database_id=database.id)
            .first()
        )
        if existing:
            print(f"  dataset exists: {name}")
            continue
        table = SqlaTable(table_name=name, schema=SCHEMA, database=database)
        db.session.add(table)
        db.session.commit()
        table.fetch_metadata()  # pull columns/types
        print(f"  registered dataset: {name}")

    print("done.")
