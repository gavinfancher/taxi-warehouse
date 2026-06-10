'''Download NYC TLC trip record parquet files for a given year.'''

import argparse
import re
import sys
from pathlib import Path

import httpx

TLC_PAGE_URL = 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page'
PARQUET_URL_PATTERN = re.compile(
    r'https://d37ci6vzurychx\.cloudfront\.net/trip-data/[^"\s]+\.parquet'
)
BROWSER_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fetch_parquet_urls(client: httpx.Client) -> list[str]:
    response = client.get(TLC_PAGE_URL)
    response.raise_for_status()
    return sorted(set(PARQUET_URL_PATTERN.findall(response.text)))


def urls_for_year(urls: list[str], year: int) -> list[str]:
    year_prefix = f'_{year:04d}-'
    return [url for url in urls if year_prefix in url.split('/')[-1]]


def download_file(client: httpx.Client, url: str, dest: Path) -> None:
    with client.stream('GET', url, follow_redirects=True) as response:
        response.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('wb') as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Download NYC TLC trip record parquet files for a given year.'
    )
    parser.add_argument(
        'year',
        type=int,
        help='Four-digit year to download (e.g. 2020)',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Directory for downloads (default: data/<year> under repo root)',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-download files even if they already exist locally',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='List matching parquet URLs without downloading',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.year < 2009 or args.year > 2100:
        print(f'Invalid year: {args.year}', file=sys.stderr)
        return 1

    output_dir = args.output_dir or repo_root() / 'data' / str(args.year)
    headers = {'User-Agent': BROWSER_USER_AGENT}

    with httpx.Client(headers=headers, timeout=httpx.Timeout(60.0, connect=30.0)) as client:
        print(f'Fetching parquet links from {TLC_PAGE_URL}...')
        parquet_urls = fetch_parquet_urls(client)
        year_urls = urls_for_year(parquet_urls, args.year)

        if not year_urls:
            print(f'No parquet files found for {args.year} on the TLC data page.', file=sys.stderr)
            return 1

        print(f'Found {len(year_urls)} parquet file(s) for {args.year}:')
        for url in year_urls:
            print(f'  {url.split("/")[-1]}')

        if args.dry_run:
            return 0

        downloaded = 0
        skipped = 0
        for url in year_urls:
            filename = url.split('/')[-1]
            dest = output_dir / filename
            if dest.exists() and not args.force:
                print(f'Skipping {filename} (already exists)')
                skipped += 1
                continue

            print(f'Downloading {filename}...')
            download_file(client, url, dest)
            downloaded += 1
            print(f'  -> {dest}')

    print(f'Done. Downloaded {downloaded}, skipped {skipped}. Output: {output_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
