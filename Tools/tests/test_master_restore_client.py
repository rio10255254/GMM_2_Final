"""A mismatched source clone must fail before large downloads or user writes."""
import importlib.util
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('restore_master_client', TOOLS / 'restore_project_from_master.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

from research_asset_bundle import pack


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            json.dump(value, stream)
    else:
        path.write_text(json.dumps(value), encoding='utf-8')


def recovery_fixture(tmp_path, monkeypatch, files, repository_aliases=(), original=None, references=None):
    """Run the real client, ZIP restore and child tools with a local transport."""
    source = tmp_path / 'captured_source'
    source.mkdir()
    for relative, data in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    selection = tmp_path / 'selection.json'
    save_json(selection, {'reviewed': True, 'files': [{'path': name, 'reason': 'original test observation'} for name in files]})
    bundle = tmp_path / 'server_objects'
    component = pack(source, selection, bundle, 200_000)
    metadata = tmp_path / 'master_metadata'
    metadata.mkdir()
    manifest = metadata / 'COMPONENT.json.gz'
    save_json(manifest, component)
    aliases = metadata / 'ALIASES.json.gz'
    save_json(aliases, {'state': 'complete', 'files': list(repository_aliases)})
    root = tmp_path / 'fresh_source'
    root.mkdir()
    catalog = root / 'docs/reproducibility/REPOSITORY_FILES.json.gz'
    save_json(catalog, {'fixture_fixed_source': True})
    master = {'state': 'complete', 'source_repository_catalog_sha256': sha(catalog.read_bytes()),
              'components': [{'tag': 'fixture-verified', 'restore_manifest': manifest.name,
                              'manifest_sha256': sha(manifest.read_bytes())}],
              'repository_alias_manifest': aliases.name,
              'repository_alias_manifest_sha256': sha(aliases.read_bytes()),
              'original_large_packages': []}
    assets = {row['name']: {**row, 'size': row['bytes'], 'digest': 'sha256:' + row['sha256'], 'state': 'uploaded'}
              for row in component['assets']}
    if original is not None:
        relative, data = original
        split = len(data) // 2
        parts = []
        for number, block in enumerate([data[:split], data[split:]], 1):
            name = 'original.zip.part' + str(number)
            (bundle / name).write_bytes(block)
            row = {'name': name, 'bytes': len(block), 'sha256': sha(block)}
            parts.append(row)
            assets[name] = {**row, 'size': len(block), 'digest': 'sha256:' + row['sha256'], 'state': 'uploaded'}
        package_manifest = metadata / 'ORIGINAL.json'
        save_json(package_manifest, {'state': 'complete', 'parts': parts,
                                    'original_bytes': len(data), 'original_sha256': sha(data)})
        master['original_large_packages'].append({'path': relative, 'tag': 'fixture-verified',
            'manifest': package_manifest.name, 'manifest_sha256': sha(package_manifest.read_bytes()),
            'original_bytes': len(data), 'original_sha256': sha(data)})
    if references is not None:
        relative = 'docs/reproducibility/research_path_aliases.json'
        save_json(root / relative, references)
        master['within_project_references_manifest'] = relative
    master_path = metadata / 'MASTER_RESTORE_INDEX.json'
    save_json(master_path, master)
    requests = []

    def server_output(command, **kwargs):
        if command == ['gh', 'auth', 'token']:
            return 'test-token-not-a-credential'
        if command[:3] == ['gh', 'release', 'view']:
            return json.dumps({'databaseId': 1}).encode()
        if command[:2] == ['gh', 'api']:
            return json.dumps({'draft': False, 'assets': list(assets.values())}).encode()
        raise AssertionError('Unexpected external command: ' + repr(command))

    def local_download(repo, asset, destination, token):
        assert repo == 'fixture/private' and token == 'test-token-not-a-credential'
        data = (bundle / asset['name']).read_bytes()
        assert len(data) == asset['size'] and sha(data) == asset['digest'][7:]
        path = destination / asset['name']
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
        requests.append(asset['name'])
        return {'name': asset['name'], 'bytes': len(data), 'sha256': sha(data)}

    monkeypatch.setattr(client.subprocess, 'check_output', server_output)
    monkeypatch.setattr(client, 'download_asset', local_download)

    def run(name, prefixes=()):
        report = tmp_path / (name + '.json')
        command = ['restore', '--repo', 'fixture/private', '--master-index', str(master_path),
                   '--root', str(root), '--downloads', str(tmp_path / 'download_cache'), '--report', str(report)]
        for prefix in prefixes:
            command += ['--prefix', prefix]
        monkeypatch.setattr(sys, 'argv', command)
        client.main()
        return json.loads(report.read_text(encoding='utf-8'))

    return root, run, requests, manifest


def test_different_source_version_stops_before_network_or_data_creation(tmp_path, monkeypatch):
    manifest = tmp_path / 'MASTER_RESTORE_INDEX.json'
    manifest.write_text(json.dumps({'state': 'complete', 'source_repository_catalog_sha256': 'a' * 64}), encoding='utf-8')
    root, downloads, report = tmp_path / 'wrong_source', tmp_path / 'downloads', tmp_path / 'report.json'
    monkeypatch.setattr(sys, 'argv', ['restore', '--repo', 'fixture/private', '--master-index', str(manifest),
                                    '--root', str(root), '--downloads', str(downloads), '--report', str(report)])
    monkeypatch.setattr(client.subprocess, 'check_output', lambda *args, **kwargs: pytest.fail('Do not contact a server for the wrong source version'))
    with pytest.raises(ValueError, match='fresh clone'):
        client.main()
    assert not root.exists() and not downloads.exists() and not report.exists()


def test_master_multiple_scopes_retry_and_user_edit_preserve_prior_results(tmp_path, monkeypatch):
    files = {'Experiments/R93/results/steps.csv': b'step,value\n1,-2.75\n',
             'Experiments/R94/results/pixels.bin': bytes(range(256))}
    original_method = b'original frozen method\n'
    alias = {'path': 'Historical_sources/original_method.py', 'provider_path': 'docs/current_method.py',
             'bytes': len(original_method), 'sha256': sha(original_method), 'git_blob': 'a' * 40}
    root, run, requests, _ = recovery_fixture(tmp_path, monkeypatch, files, [alias])
    (root / 'docs/current_method.py').write_bytes(original_method)
    first = run('first', ['Experiments/R93'])
    assert first['components'][0]['restoration']['files_restored_and_verified'] == 1
    receipt_paths = list(root.glob('RESTORE_*_VERIFIED.json')) + list((tmp_path / 'download_cache').glob('*.json'))
    receipts = {p: p.read_bytes() for p in receipt_paths}
    assert receipts
    run('second', ['Experiments/R94'])
    retry = run('retry', ['Experiments/R94'])
    assert retry['components'][0]['restoration']['identical_existing_files_reused'] == 1
    run('historical_method', ['Historical_sources'])
    assert (root / alias['path']).read_bytes() == original_method
    assert all(path.read_bytes() == data for path, data in receipts.items())
    assert (root / 'Experiments/R93/results/steps.csv').read_bytes() == files['Experiments/R93/results/steps.csv']
    target = root / 'Experiments/R94/results/pixels.bin'
    target.write_bytes(b'user revised result')
    with pytest.raises(FileExistsError, match='differs'):
        run('must_not_replace_user_result', ['Experiments/R94'])
    assert target.read_bytes() == b'user revised result'
    assert not (tmp_path / 'must_not_replace_user_result.json').exists()
    assert requests


def test_master_original_distribution_roundtrip_and_user_file_protection(tmp_path, monkeypatch):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('README.txt', b'original delivery, unchanged')
        archive.writestr('camera/input.bmp', bytes(range(256)) * 2)
    original = stream.getvalue()
    relative = 'Original_deliveries/research.zip'
    root, run, _, _ = recovery_fixture(tmp_path, monkeypatch,
        {'Experiments/R93/result.csv': b'1,2,3\n'}, original=(relative, original))
    result = run('distribution', ['Original_deliveries'])
    assert result['original_large_packages'][0]['original_sha256'] == sha(original)
    target = root / relative
    assert target.read_bytes() == original
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    retry = run('distribution_retry', ['Original_deliveries'])
    assert retry['original_large_packages'][0]['identical_existing']
    target.write_bytes(b'user owned replacement')
    with pytest.raises(FileExistsError, match='Existing original package differs'):
        run('must_not_replace_distribution', ['Original_deliveries'])
    assert target.read_bytes() == b'user owned replacement'


def test_master_full_client_reconnects_the_eleven_real_shared_path_shapes(tmp_path, monkeypatch):
    references = json.loads((TOOLS.parent / 'docs/reproducibility/research_path_aliases.json').read_text(encoding='utf-8'))
    links = [row for row in references['links'] if row['kind'] == 'inside_project']
    assert len(links) == 11
    targets = {row['portable_target'] for row in links}
    files = {target + '/fixture_observation.csv': b'frame,value\n1,0.125\n' for target in targets}
    root, run, _, _ = recovery_fixture(tmp_path, monkeypatch, files, references=references)
    first = run('full_fixture')
    assert len(first['within_project_references']['created']) == 11
    for row in links:
        assert (root / row['path']).resolve() == (root / row['portable_target']).resolve()
        assert (root / row['path'] / 'fixture_observation.csv').read_bytes() == b'frame,value\n1,0.125\n'
    for row in references['links']:
        if row['kind'] != 'inside_project':
            assert not (root / row['path']).exists()
    old_reports = {p: p.read_bytes() for p in (tmp_path / 'download_cache').glob('*.json')}
    assert len(old_reports) == 2
    assert sum(p.name.startswith('WITHIN_PROJECT_REFERENCES_') for p in old_reports) == 1
    second = run('full_fixture_retry')
    assert len(second['within_project_references']['already_correct']) == 11
    assert all(path.read_bytes() == data for path, data in old_reports.items())


def test_master_changed_component_metadata_refused_before_restored_output(tmp_path, monkeypatch):
    root, run, requests, manifest = recovery_fixture(tmp_path, monkeypatch,
        {'Experiments/R93/result.csv': b'1,2,3\n'})
    manifest.write_bytes(manifest.read_bytes() + b'changed metadata')
    with pytest.raises(ValueError, match='Master restore metadata differs'):
        run('must_reject_changed_map', ['Experiments/R93'])
    assert not requests
    assert not (root / 'Experiments').exists()
