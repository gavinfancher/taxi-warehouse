'''Download NYC TLC trip record parquet files.'''

import time
from pathlib import Path

import httpx
from tqdm import tqdm

BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'
YEAR = 2025
CATEGORIES = ['yellow', 'green', 'fhv', 'fhvhv']
MONTHS = range(1, 13)
CHUNK_SIZE = 1024 * 256
BAR_FORMAT = '{desc}{percentage:4.0f}%|{bar:28}|{postfix}'
SIZE_WIDTH = 9
TIME_WIDTH = 7
RATE_WIDTH = 12
TERMINAL_WIDTH = 132


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_urls() -> list[str]:
    urls: list[str] = []
    for category in CATEGORIES:
        for month in MONTHS:
            urls.append(
                f'{BASE_URL}/{category}_tripdata_{YEAR}-{month:02d}.parquet'
            )
    return urls


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
        return tqdm.format_sizeof(num, suffix='B', divisor=1024).rjust(SIZE_WIDTH)

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
                f'{tqdm.format_sizeof(rate, suffix="B", divisor=1024)}/s'
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
    destination: Path,
    *,
    layout: DownloadLayout,
    index: int,
) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with client.stream('GET', url, follow_redirects=True) as response:
        downloaded = 0
        success = False
        interrupted = False
        byte_total = 0
        bar = AlignedTqdm(
            total=None,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=layout.label(index, destination.name),
            leave=True,
            dynamic_ncols=False,
            ncols=TERMINAL_WIDTH,
        )
        try:
            response.raise_for_status()
            byte_total = int(response.headers.get('content-length', 0))
            if byte_total:
                bar.total = byte_total
                bar.refresh()
            with destination.open('wb') as handle:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    bar.update(len(chunk))
            success = True
        except KeyboardInterrupt:
            interrupted = True
            if destination.exists():
                destination.unlink()
            raise
        finally:
            if not byte_total and downloaded:
                bar.total = downloaded
            bar.refresh_stats()
            if success:
                bar.colour = 'green'
            elif interrupted:
                bar.colour = 'yellow'
            else:
                bar.colour = 'red'
            bar.refresh()
            bar.close()

    return downloaded


def main() -> int:
    output_dir = repo_root() / 'data' / 'parquet'
    urls = build_urls()
    filenames = [url.split('/')[-1] for url in urls]
    layout = DownloadLayout(filenames)
    downloaded = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    bytes_downloaded = 0
    started = time.perf_counter()
    interrupted = False
    interrupted_label = ''

    print()
    print(f'found {len(urls)} files for {YEAR} -> data/parquet')

    with httpx.Client(timeout=120.0) as client:
        try:
            for index, url in enumerate(urls, start=1):
                filename = url.split('/')[-1]
                destination = output_dir / filename
                interrupted_label = layout.label(index, filename)

                if destination.exists():
                    skipped += 1
                    continue

                try:
                    size = download_file(
                        client, url, destination, layout=layout, index=index
                    )
                    bytes_downloaded += size
                    downloaded += 1
                except httpx.HTTPError as exc:
                    failed.append((filename, str(exc)))
                    if destination.exists():
                        destination.unlink()
                    tqdm.write(f'{layout.label(index, filename)}  fail: {exc}')
        except KeyboardInterrupt:
            interrupted = True
            print()
            print(f'{interrupted_label}  interrupted by user')

    print()
    print('summary')
    print(f'  year:        {YEAR}')
    print('  output:      data/parquet')
    print(f'  downloaded:  {downloaded}')
    print(f'  skipped:     {skipped}')
    print(f'  failed:      {len(failed)}')
    if downloaded:
        elapsed = time.perf_counter() - started
        print(f'  transferred: {format_bytes(bytes_downloaded)}')
        print(f'  duration:    {elapsed:.1f}s')
    if interrupted:
        print('  interrupted: yes')
        return 130
    if failed:
        for filename, message in failed:
            print(f'  - {filename}: {message}')
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
