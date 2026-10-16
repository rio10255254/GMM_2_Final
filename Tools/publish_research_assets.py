"""Upload completed, locally hashed bundles to an authorized private draft release.

Publishing the draft is deliberately a separate action after restore validation.
Existing assets must match; this tool never replaces an uploaded asset.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import time
import zipfile

from research_recovery import digest, write_json


def command(arguments):
    result = subprocess.run(['gh', *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('GitHub command failed: ' + ' '.join(arguments[:3]))
    return result.stdout.decode('utf-8')


def release_state(repo, tag):
    return json.loads(command(['release', 'view', tag, '--repo', repo,
                               '--json', 'isDraft,url,tagName,assets,databaseId']))


def upload_one(repo, tag, path):
    checksum = digest(path); size = path.stat().st_size
    state = release_state(repo, tag)
    prior = next((asset for asset in state['assets'] if asset['name'] == path.name), None)
    if prior is None:
        command(['release', 'upload', tag, str(path), '--repo', repo])
    state = release_state(repo, tag)
    asset = next(asset for asset in state['assets'] if asset['name'] == path.name)
    actual = asset.get('digest')
    if actual != 'sha256:' + checksum or asset['size'] != size:
        raise ValueError('GitHub uploaded asset differs: ' + path.name)
    print('UPLOADED_SERVER_SHA256_VERIFIED', tag, path.name, size, flush=True)
    return {'name': path.name, 'bytes': size, 'sha256': checksum,
            'github_digest': actual, 'github_asset_id': asset['id']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True); parser.add_argument('--tag', required=True)
    parser.add_argument('--title', required=True); parser.add_argument('--target', required=True)
    parser.add_argument('--bundle', type=Path, required=True); parser.add_argument('--watch', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    identity = json.loads(command(['repo', 'view', args.repo, '--json', 'isPrivate']))
    if not identity['isPrivate']:
        raise ValueError('This authorized collection is intended for the private repository')
    existing = subprocess.run(['gh','release','view',args.tag,'--repo',args.repo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if existing.returncode:
        command(['release','create',args.tag,'--repo',args.repo,'--draft','--target',args.target,
                 '--title',args.title,'--notes','保存整理中；完成來源、還原與GitHub內容核對後才正式發布。'])
    state = release_state(args.repo, args.tag)
    if not state['isDraft']:
        raise ValueError('Upload work requires the original draft release')
    receipt = args.bundle / 'GITHUB_UPLOAD_VERIFIED.json'
    if receipt.exists():
        raise FileExistsError('Upload receipt already exists')
    futures = {}; rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            complete = (args.bundle / 'BUNDLE_SUMMARY.json').is_file()
            for path in sorted(args.bundle.glob('research-*.zip')):
                if path.name in futures:
                    continue
                try:
                    with zipfile.ZipFile(path) as archive:
                        if not archive.namelist():
                            continue
                except (OSError, zipfile.BadZipFile):
                    continue
                futures[path.name] = pool.submit(upload_one, args.repo, args.tag, path)
            if complete:
                break
            if not args.watch:
                raise ValueError('Bundle is incomplete; use --watch only for the running pack operation')
            time.sleep(5)
        for future in futures.values():
            rows.append(future.result())
    summary = json.loads((args.bundle / 'BUNDLE_SUMMARY.json').read_text(encoding='utf-8'))
    assert {row['name'] for row in rows} == {row['name'] for row in summary['assets']}
    for expected in summary['assets']:
        actual = next(row for row in rows if row['name'] == expected['name'])
        assert actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes']
    sums = args.bundle / 'SHA256SUMS.txt'
    if not sums.exists():
        sums.write_text(''.join(digest(path)+'  '+path.name+'\n' for path in sorted(args.bundle.iterdir())
                                if path.suffix == '.zip' or path.name in {'RESEARCH_ASSETS.json.gz','BUNDLE_SUMMARY.json'}), encoding='utf-8')
    for name in ['RESEARCH_ASSETS.json.gz','BUNDLE_SUMMARY.json','SHA256SUMS.txt']:
        rows.append(upload_one(args.repo, args.tag, args.bundle / name))
    write_json(receipt, {'status':'PASS','repo':args.repo,'tag':args.tag,
                        'release_is_draft':True,'assets':rows,'all_server_sha256_match_local':True})


if __name__ == '__main__':
    main()
