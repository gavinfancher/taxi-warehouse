import time

import duckdb

DB = 'data/db/local.duckdb'
DATA = 'data/parquet'

TABLES = {
    'yellow': 'yellow_trips',
    'green': 'green_trips',
    'fhv': 'fhv_trips',
    'fhvhv': 'fhvhv_trips',
}

con = duckdb.connect(DB)
started = time.perf_counter()
label_width = max(len(t) for t in TABLES.values())

print()
for category, table in TABLES.items():
    path_glob = f'{DATA}/{category}_tripdata_2025-*.parquet'
    t0 = time.perf_counter()
    con.execute(f"""
        create or replace table {table} as
        select *
        from read_parquet('{path_glob}', union_by_name=true)
    """)
    elapsed = time.perf_counter() - t0
    print(f'  {table:<{label_width}}  {elapsed:>5.1f}s')

con.close()
total = time.perf_counter() - started
print()
print(f'done -> {DB} ({total:.1f}s)')
