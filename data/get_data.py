'''Download NYC TLC trip record parquet files for 2025 only.'''

from pathlib import Path

import httpx
from tqdm import tqdm

BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'
CATEGORIES = ['yellow', 'green', 'fhv', 'fhvhv']
MONTHS = range(1, 13)
CHUNK_SIZE = 1024 * 256


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_urls() -> list[str]:
    urls: list[str] = []
    for category in CATEGORIES:
        for month in MONTHS:
            urls.append(
                f'{BASE_URL}/{category}_tripdata_2025-{month:02d}.parquet'
            )
    return urls


def download_file(client: httpx.Client, url: str, destination: Path, filename: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with client.stream('GET', url, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        with destination.open('wb') as handle:
            with tqdm(
                total=total if total > 0 else None,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=filename,
                leave=True,
            ) as progress:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    handle.write(chunk)
                    progress.update(len(chunk))


def main() -> int:
    output_dir = repo_root() / 'data' / 'parquet'
    urls = build_urls()
    downloaded = 0
    skipped = 0
    failed: list[str] = []

    with httpx.Client(timeout=120.0) as client:
        for url in urls:
            filename = url.split('/')[-1]
            destination = output_dir / filename

            if destination.exists():
                skipped += 1
                print(f'skip {filename}')
                continue

            try:
                print(f'download {filename}')
                download_file(client, url, destination, filename)
                downloaded += 1
            except httpx.HTTPError as exc:
                failed.append(f'{filename}: {exc}')
                if destination.exists():
                    destination.unlink()
                print(f'fail {filename}: {exc}')

    print()
    print('summary')
    print('  year: 2025')
    print(f'  output: {output_dir}')
    print(f'  downloaded: {downloaded}')
    print(f'  skipped: {skipped}')
    print(f'  failed: {len(failed)}')
    if failed:
        for error in failed:
            print(f'  - {error}')
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
