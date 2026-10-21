"""Fetch one exact preserved object without downloading its whole ZIP part.

Only ZIP headers, its central directory and the selected compressed member are
requested. The original object must match its complete SHA-256 and size before
it receives its final name. Existing files are never overwritten. Authentication
and temporary signed URLs remain in memory and never appear in reports.
"""
import argparse
import hashlib
import io
import os
import re
from pathlib import Path
import subprocess
import time
import zipfile

import requests

from download_research_assets import bounded_range
from verify_project_release_assets import read, release_snapshot, check_assets
from research_recovery import write_json


class RangeReader:
    """A bounded, seekable view for Python's ZIP/ZIP64 reader."""
    def __init__(self, size, fetch):
        self.size = size
        self.fetch = fetch
        self.position = 0
        self.requested_bytes = 0
        self.requests = 0
        self.received_ranges = []

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        position = offset if whence == io.SEEK_SET else self.position + offset if whence == io.SEEK_CUR else self.size + offset if whence == io.SEEK_END else -1
        if position < 0:
            raise ValueError('Invalid archive seek')
        self.position = position
        return position

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        size = min(size, max(0, self.size - self.position))
        if not size:
            return b''
        # Avoid accidentally using a whole-part API when the ZIP reader asks
        # for a large block. Individual requests stay bounded at 4 MiB.
        chunks = []
        while size:
            count = min(size, 4 * 1024**2)
            start = self.position
            data = self.fetch(start, start + count - 1)
            if len(data) != count:
                raise ValueError('Incomplete selected archive range')
            chunks.append(data)
            self.position += count
            self.requested_bytes += count
            self.requests += 1
            self.received_ranges.append((start, start + count))
            size -= count
        return b''.join(chunks)


def restore_member(reader, sha256, expected_bytes, output):
    partial = Path(str(output) + '.part')
    if output.exists() or partial.exists():
        raise FileExistsError('Keep an existing object or earlier partial download')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(reader) as archive:
        name = 'objects/' + sha256
        matches = [info for info in archive.infolist() if info.filename == name]
        if len(matches) != 1 or matches[0].file_size != expected_bytes or matches[0].flag_bits & 1:
            raise ValueError('Selected original object is absent, ambiguous or differs in size')
        digest = hashlib.sha256()
        size = 0
        with archive.open(matches[0]) as stream, partial.open('xb') as destination:
            while block := stream.read(1024**2):
                destination.write(block)
                digest.update(block)
                size += len(block)
    if (size, digest.hexdigest()) != (expected_bytes, sha256):
        raise ValueError('Selected restored original object differs from its frozen identity')
    with partial.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != sha256:
            raise ValueError('The written selected object differs')
    # POSIX rename replaces an existing destination. Publish without that
    # behavior, including when another process creates a file during download.
    if os.name == 'nt':
        os.rename(partial, output)
    else:
        os.link(partial, output)
        partial.unlink()
    coverage = 0
    end = 0
    for start, stop in sorted(reader.received_ranges):
        coverage += max(0, stop - max(start, end))
        end = max(end, stop)
    return {'bytes': size, 'sha256': sha256, 'range_bytes_received': reader.requested_bytes,
            'range_requests': reader.requests, 'unique_archive_bytes_received': coverage,
            'entire_archive_part_downloaded': coverage == reader.size}


def download_object(repo, tag, manifest_path, sha256, output, allow_draft=False):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Name one explicit GitHub repository')
    if output.exists() or Path(str(output) + '.part').exists():
        raise FileExistsError('Keep an existing object or earlier partial download')
    if not re.fullmatch(r'[0-9a-f]{64}', sha256):
        raise ValueError('Provide the exact original object SHA-256')
    manifest = read(manifest_path)
    if manifest.get('state') != 'complete':
        raise ValueError('An exact complete object manifest is required')
    matches = [row for row in manifest['files'] if row['sha256'] == sha256]
    if not matches or len({(row['asset'], row['bytes']) for row in matches}) != 1:
        raise ValueError('The manifest has no unambiguous provider for this object')
    name, size = matches[0]['asset'], matches[0]['bytes']
    specs = [row for row in manifest['assets'] if row['name'] == name]
    if len(specs) != 1:
        raise ValueError('One exact archive-part specification is required')
    snapshot = release_snapshot(repo, tag, allow_draft=allow_draft)
    check_assets(specs, snapshot)
    asset = next(row for row in snapshot['assets'] if row['name'] == name)
    token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream',
               'X-GitHub-Api-Version': '2022-11-28'}
    endpoint = 'https://api.github.com/repos/' + repo + '/releases/assets/' + str(asset['id'])
    try:
        with requests.get(endpoint, headers=headers, allow_redirects=False, stream=True, timeout=(30, 30)) as response:
            if response.status_code != 302:
                raise RuntimeError('The ranged archive download endpoint did not redirect')
            signed_url = response.headers['Location']
        def fetch(start, end):
            for attempt in range(4):
                try:
                    return bounded_range(signed_url, {'Accept': 'application/octet-stream'}, start, end, asset['size'])
                except (requests.RequestException, RuntimeError, OSError, ValueError):
                    if attempt == 3:
                        raise RuntimeError('A selected archive range could not be verified') from None
                    time.sleep(min(2**attempt, 8))
        reader = RangeReader(asset['size'], fetch)
        result = restore_member(reader, sha256, size, output)
    except requests.RequestException:
        raise RuntimeError('The archive connection failed; authentication details omitted') from None
    return {'status': 'PASS_SELECTED_OBJECT_ACTUALLY_FETCHED_AND_RESTORED', 'repo': repo, 'tag': tag,
            'asset': name, 'asset_id': asset['id'], 'asset_bytes': asset['size'],
            'asset_sha256_matched_to_server_metadata': specs[0]['sha256'],
            'release_was_draft': snapshot['draft'], 'actual_asset_listing_pages': snapshot['server_pages'],
            'complete_archive_SHA256_recomputed_by_this_partial_operation': False,
            'whole_project_complete': False, **result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-draft', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() in {args.output.resolve(), Path(str(args.output) + '.part').resolve()}:
        raise ValueError('The receipt cannot overwrite its restored data or partial file')
    if args.report.exists():
        raise FileExistsError('Preserve the earlier object recovery receipt')
    result = download_object(args.repo, args.tag, args.manifest, args.sha256, args.output, args.allow_draft)
    write_json(args.report, result)
    print('ONE_PRESERVED_OBJECT_ACTUALLY_RECOVERED', result['bytes'], result['range_bytes_received'], flush=True)
