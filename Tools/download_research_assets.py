"""Download private research release assets and verify GitHub's SHA-256 digest.

Authentication stays in memory. Signed download URLs and tokens are never logged.
Existing verified files are reused; existing unverified final files are refused.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import time

import requests


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bounded_range(url, headers, offset, end, size):
    headers = dict(headers, Range=f'bytes={offset}-{end}')
    with requests.get(url, headers=headers, stream=True, timeout=(30, 60)) as response:
        if response.status_code == 206:
            if response.headers.get('Content-Range') != f'bytes {offset}-{end}/{size}':
                raise ValueError('Unexpected partial download range')
            data = response.content
            if len(data) != end - offset + 1:
                raise ValueError('Incomplete bounded download range')
        elif response.status_code == 200 and offset == 0 and size <= end + 1:
            data = response.content
            if len(data) != size:
                raise ValueError('Incomplete full asset response')
        else:
            raise RuntimeError('Asset HTTP status ' + str(response.status_code))
    return data


def download_asset(repo, asset, output, token):
    name = asset['name']
    if Path(name).name != name or ':' in name or name in {'.', '..'}:
        raise ValueError('Unsafe release asset filename')
    target = output / name
    expected = asset.get('digest', '')
    if not expected.startswith('sha256:'):
        raise ValueError('Release asset has no SHA-256 digest: ' + name)
    expected = expected[7:]
    if target.exists():
        if target.stat().st_size != asset['size'] or sha(target) != expected:
            raise FileExistsError('Existing final asset differs: ' + name)
    else:
        partial = output / (name + '.part')
        for attempt in range(4):
            try:
                offset = partial.stat().st_size if partial.exists() else 0
                headers = {'Authorization': 'Bearer ' + token,
                           'Accept': 'application/octet-stream',
                           'X-GitHub-Api-Version': '2022-11-28'}
                url = 'https://api.github.com/repos/' + repo + '/releases/assets/' + str(asset['id'])
                with requests.get(url, headers=headers, allow_redirects=False, stream=True,
                                  timeout=(30, 30)) as redirect:
                    if redirect.status_code == 302:
                        # Keep the temporary URL in memory; never write it to
                        # a command line, exception, manifest or progress log.
                        url = redirect.headers['Location']
                        headers = {'Accept': 'application/octet-stream'}
                # Bounded ranges also work through connections that stall on
                # a multi-gigabyte streaming response. Each written range is
                # complete, so retries can resume from an exact byte offset.
                with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ranges:
                    while offset < asset['size']:
                        starts = range(offset, min(offset + 32 * 1024**2, asset['size']), 1024**2)
                        futures = [ranges.submit(bounded_range, url, headers, start,
                                                 min(start + 1024**2, asset['size']) - 1,
                                                 asset['size']) for start in starts]
                        for future in futures:
                            data = future.result()
                            with partial.open('ab') as stream:
                                stream.write(data)
                            offset += len(data)
                            if offset // (256 * 1024**2) != (offset - len(data)) // (256 * 1024**2):
                                print('GITHUB_ASSET_PROGRESS', name, offset, asset['size'], flush=True)
                if partial.stat().st_size != asset['size']:
                    raise ValueError('Incomplete asset: ' + name)
                if sha(partial) != expected:
                    raise ValueError('Asset SHA-256 mismatch: ' + name)
                partial.rename(target)
                break
            except (requests.RequestException, RuntimeError, OSError, ValueError) as error:
                # Do not echo requests errors: they can include signed URLs.
                print('RETRY', name, type(error).__name__, attempt + 1, flush=True)
                if attempt == 3:
                    raise RuntimeError('Download or verification failed: ' + name) from None
                time.sleep(min(2 ** attempt, 8))
    print('GITHUB_ASSET_VERIFIED', name, asset['size'], flush=True)
    return {'name': name, 'bytes': asset['size'], 'sha256': expected,
            'asset_id': asset['id'], 'verified_from_github': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
    identity = json.loads(subprocess.check_output(
        ['gh', 'release', 'view', args.tag, '--repo', args.repo, '--json', 'databaseId'],
        text=True, encoding='utf-8'))
    # Draft tags need the release ID endpoint until their tag is published.
    release = json.loads(subprocess.check_output(
        ['gh', 'api', 'repos/' + args.repo + '/releases/' + str(identity['databaseId'])],
        text=True, encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    report = args.output / 'GITHUB_ASSETS_VERIFIED.json'
    if report.exists():
        raise FileExistsError('Verification receipt already exists')
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download_asset, args.repo, asset, args.output, token) for asset in release['assets']]
        rows = [future.result() for future in futures]
    report.write_text(json.dumps({'status': 'PASS', 'repo': args.repo, 'tag': args.tag,
                                  'release_was_draft': release['draft'], 'assets': rows,
                                  'seconds': time.perf_counter() - started},
                                 ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
