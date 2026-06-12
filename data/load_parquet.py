import duckdb

DB = 'data/local.duckdb'
DATA = 'data'

CATEGORIES = ['yellow', 'green', 'fhv', 'fhvhv']

con = duckdb.connect(DB)

for category in CATEGORIES:
    glob = f'{DATA}/*/{category}_tripdata_*.parquet'
    table = f'{category}_trips'

    con.execute(f"""
        create or replace table {table} as
        select *
        from read_parquet('{glob}', union_by_name=true)
    """)

    rows = con.execute(f'select count(*) from {table}').fetchone()[0]
    print(f'{table}: {rows:,} rows')

con.close()
print(f'done -> {DB}')
