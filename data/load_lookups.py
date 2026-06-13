'''Load lookup tables from SQL files into DuckDB.'''

import time
from pathlib import Path

import duckdb

DB = 'data/db/local.duckdb'
SQL_DIR = Path('data/sql')

SQL_FILES = [
    'rideshare_lookup.sql',
    'trip_lookup.sql',
    'zones_lookup.sql'
]

con = duckdb.connect(DB)
started = time.perf_counter()
label_width = max(len(f) for f in SQL_FILES)

print()
for filename in SQL_FILES:
    path = SQL_DIR / filename
    sql = path.read_text()
    t0 = time.perf_counter()
    for statement in sql.split(';'):
        statement = statement.strip()
        if statement:
            con.execute(statement)
    elapsed = time.perf_counter() - t0
    print(f'  {filename:<{label_width}}  {elapsed:>5.1f}s')

con.close()
total = time.perf_counter() - started
print()
print(f'done -> {DB} ({total:.1f}s)')
