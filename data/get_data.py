'''Download NYC TLC trip record parquet files for a given year.'''

import argparse
import re
import sys
import time
from pathlib import Path

import httpx
from tqdm import tqdm

TLC_PAGE_URL = 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page'
PARQUET_URL_PATTERN = re.compile(
    r'https://d37ci6vzurychx\.cloudfront\.net/trip-data/[^"\s]+\.parquet'
)
BROWSER_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
BAR_FORMAT = '{desc}{percentage:4.0f}%|{bar:28}|{postfix}'
SIZE_WIDTH = 7
TIME_WIDTH = 7
RATE_WIDTH = 10
TERMINAL_WIDTH = 132


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fetch_parquet_urls(client: httpx.Client) -> list[str]:
    response = client.get(TLC_PAGE_URL)
    response.raise_for_status()
    return sorted(set(PARQUET_URL_PATTERN.findall(response.text)))


def urls_for_year(urls: list[str], year: int) -> list[str]:
    year_prefix = f'_{year:04d}-'
    return [url for url in urls if year_prefix in url.split('/')[-1]]


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f'{num_bytes} B'
    if num_bytes < 1024 ** 2:
        return f'{num_bytes / 1024:.1f} KB'
    if num_bytes < 1024 ** 3:
        return f'{num_bytes / 1024 ** 2:.1f} MB'
    return f'{num_bytes / 1024 ** 3:.2f} GB'


class DownloadLayout:
    def __init__(self, filenames: list[str]) -> None:
        self.total_files = len(filenames)
        self.index_width = len(str(self.total_files))
        self.filename_width = max(len(name) for name in filenames)

    def label(self, index: int, filename: str) -> str:
        counter = f'[{index:>{self.index_width}}/{self.total_files}]'
        return f'{counter} {filename:<{self.filename_width}}'


class AlignedTqdm(tqdm):
    @classmethod
    def format_sizeof(cls, num, suffix='', divisor=1024):
        if num is None:
            return '?'.rjust(SIZE_WIDTH)
        return tqdm.format_sizeof(num, suffix, divisor).rjust(SIZE_WIDTH)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('bar_format', BAR_FORMAT)
        super().__init__(*args, **kwargs)
        self.refresh_stats(elapsed_s=0, rate=None)

    def _format_stats(self, n, total, elapsed_s, rate):
        n_fmt = self.format_sizeof(n, divisor=self.unit_divisor)
        total_fmt = (
            self.format_sizeof(total, divisor=self.unit_divisor)
            if total
            else '?'.rjust(SIZE_WIDTH)
        )
        elapsed_str = tqdm.format_interval(elapsed_s).rjust(TIME_WIDTH)
        if rate and total:
            remaining = max((total - n) / rate, 0)
            remaining_str = tqdm.format_interval(remaining).rjust(TIME_WIDTH)
            rate_fmt = (
                f'{self.format_sizeof(rate, divisor=self.unit_divisor)}/s'
            ).rjust(RATE_WIDTH)
        else:
            remaining_str = '?'.rjust(TIME_WIDTH)
            rate_fmt = '?'.rjust(RATE_WIDTH)
        return f' {n_fmt}/{total_fmt} [{elapsed_str}<{remaining_str}, {rate_fmt}]'

    def refresh_stats(self, *, elapsed_s=None, rate=None):
        if elapsed_s is None:
            elapsed_s = max(self._time() - self.start_t, 0)
        if rate is None:
            rate = (self.n / elapsed_s) if elapsed_s and self.n else None
        self.set_postfix_str(
            self._format_stats(self.n, self.total, elapsed_s, rate),
            refresh=False,
        )

    def __str__(self):
        return super().__str__().replace('|, ', '| ', 1)

    def update(self, n=1):
        result = super().update(n)
        self.refresh_stats()
        return result


def download_file(
    client: httpx.Client,
    url: str,
    dest: Path,
    *,
    layout: DownloadLayout,
    index: int,
) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    success = False
    byte_total = 0
    bar = AlignedTqdm(
        total=None,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
        desc=layout.label(index, dest.name),
        leave=True,
        dynamic_ncols=False,
        ncols=TERMINAL_WIDTH,
    )
    try:
        with client.stream('GET', url, follow_redirects=True) as response:
            response.raise_for_status()
            byte_total = int(response.headers.get('content-length', 0))
            if byte_total:
                bar.total = byte_total
                bar.refresh()
            with dest.open('wb') as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    bar.update(len(chunk))
        success = True
    finally:
        if not byte_total and downloaded:
            bar.total = downloaded
        bar.refresh_stats()
        bar.colour = 'green' if success else 'red'
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

        filenames = [url.split('/')[-1] for url in year_urls]
        layout = DownloadLayout(filenames)
        total_files = len(year_urls)
        print(f'found {total_files} file(s) for {args.year} -> {output_dir}')

        if args.dry_run:
            for index, filename in enumerate(filenames, start=1):
                print(f'  {layout.label(index, filename)}')
            return 0

        downloaded_count = 0
        skipped_count = 0
        skipped_files: list[tuple[int, str]] = []
        failed: list[tuple[str, str]] = []
        bytes_downloaded = 0
        started = time.perf_counter()

        for index, url in enumerate(year_urls, start=1):
            filename = url.split('/')[-1]
            dest = output_dir / filename

            if dest.exists() and not args.force:
                skipped_count += 1
                skipped_files.append((index, filename))
                continue

            try:
                size = download_file(
                    client, url, dest, layout=layout, index=index
                )
                bytes_downloaded += size
                downloaded_count += 1
            except httpx.HTTPError as exc:
                failed.append((filename, str(exc)))
                tqdm.write(f'{layout.label(index, filename)}  fail: {exc}')
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
            for index, filename in skipped_files:
                print(f'  {layout.label(index, filename)}')
        elif skipped_files:
            index, filename = skipped_files[0]
            print(f'  {layout.label(index, filename)}, ... (+{skipped_count - 1} more)')
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
