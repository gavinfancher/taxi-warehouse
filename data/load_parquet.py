import duckdb
from tqdm import tqdm

DB = 'data/local.duckdb'
DATA = 'data/parquet'
BAR_FORMAT = '{desc}{percentage:4.0f}%|{bar:28}|{n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
TERMINAL_WIDTH = 110

TABLES = {
    'yellow': 'yellow_trips',
    'green': 'green_trips',
    'fhv': 'fhv_trips',
    'fhvhv': 'fhvhv_trips',
}

con = duckdb.connect(DB)

with tqdm(
    total=len(TABLES),
    desc='Loading parquet tables ',
    unit='table',
    bar_format=BAR_FORMAT,
    dynamic_ncols=False,
    ncols=TERMINAL_WIDTH,
) as progress:
    for category, table in TABLES.items():
        path_glob = f'{DATA}/{category}_tripdata_2025-*.parquet'
        con.execute(
            f'create or replace table {table} as '
            f"select * from read_parquet('{path_glob}', union_by_name=true)"
        )
        rows = con.execute(f'select count(*) from {table}').fetchone()[0]
        progress.update(1)
        progress.set_postfix_str(f'{table} {rows:,} rows', refresh=True)
        tqdm.write(f'{table}: {rows:,} rows')

con.close()
print(f'done -> {DB}')
