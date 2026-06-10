'''Download NYC TLC trip record parquet files for a given year (v2).

Cleaner output with per-file progress bars similar to wget.
'''

import argparse
import sys
import time
from pathlib import Path

import httpx
from tqdm import tqdm

from get_data import (
    BROWSER_USER_AGENT,
    TLC_PAGE_URL,
    fetch_parquet_urls,
    repo_root,
    urls_for_year,
)

WGET_BAR = (
    '{desc} {percentage:3.0f}%|{bar:30}| '
    '{n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
)


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f'{num_bytes} B'
    if num_bytes < 1024 ** 2:
        return f'{num_bytes / 1024:.1f} KB'
    if num_bytes < 1024 ** 3:
        return f'{num_bytes / 1024 ** 2:.1f} MB'
    return f'{num_bytes / 1024 ** 3:.2f} GB'


def download_file(
    client: httpx.Client,
    url: str,
    dest: Path,
    *,
    index: int,
    total: int,
) -> int:
    filename = dest.name
    label = f'[{index}/{total}] {filename}'
    with client.stream('GET', url, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        dest.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        bar = tqdm(
            total=total or None,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=label,
            bar_format=WGET_BAR,
            leave=True,
            dynamic_ncols=True,
        )
        try:
            with dest.open('wb') as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    bar.update(len(chunk))
        finally:
            if not total and downloaded:
                bar.total = downloaded
                bar.refresh()
            bar.close()

    return downloaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Download NYC TLC trip record parquet files for a given year.'
    )
    parser.add_argument('year', type=int, help='Four-digit year to download (e.g. 2020)')
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
        print(f'error: invalid year {args.year}', file=sys.stderr)
        return 1

    output_dir = args.output_dir or repo_root() / 'data' / str(args.year)
    headers = {'User-Agent': BROWSER_USER_AGENT}
    timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)

    with httpx.Client(headers=headers, timeout=timeout) as client:
        print(f'scanning {TLC_PAGE_URL}')
        parquet_urls = fetch_parquet_urls(client)
        year_urls = urls_for_year(parquet_urls, args.year)

        if not year_urls:
            print(f'error: no parquet files found for {args.year}', file=sys.stderr)
            return 1

        total_files = len(year_urls)
        print(f'found {total_files} file(s) for {args.year} -> {output_dir}')

        if args.dry_run:
            for url in year_urls:
                print(f'  {url.split("/")[-1]}')
            return 0

        downloaded_count = 0
        skipped_count = 0
        skipped_files: list[str] = []
        failed: list[tuple[str, str]] = []
        bytes_downloaded = 0
        started = time.perf_counter()

        for index, url in enumerate(year_urls, start=1):
            filename = url.split('/')[-1]
            dest = output_dir / filename

            if dest.exists() and not args.force:
                skipped_count += 1
                skipped_files.append(filename)
                continue

            try:
                size = download_file(
                    client, url, dest, index=index, total=total_files
                )
                bytes_downloaded += size
                downloaded_count += 1
            except httpx.HTTPError as exc:
                failed.append((filename, str(exc)))
                tqdm.write(f'[{index}/{total_files}] fail  {filename}: {exc}')
                if dest.exists():
                    dest.unlink()

        elapsed = time.perf_counter() - started
        print()
        print('summary')
        print(f'  year:       {args.year}')
        print(f'  output:     {output_dir}')
        print(f'  downloaded: {downloaded_count}')
        print(f'  skipped:    {skipped_count}')
        if skipped_files and skipped_count <= 5:
            for filename in skipped_files:
                print(f'              {filename}')
        elif skipped_files:
            print(f'              {skipped_files[0]}, ... (+{skipped_count - 1} more)')
        print(f'  failed:     {len(failed)}')
        if downloaded_count:
            print(f'  transferred:{format_bytes(bytes_downloaded)} in {elapsed:.1f}s')
        if failed:
            print('  failures:')
            for filename, message in failed:
                print(f'    - {filename}: {message}')
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
