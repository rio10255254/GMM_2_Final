"""Verify real archive recovery, duplicate sources and refusal of corrupt inputs."""
import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_asset_bundle import pack, restore, verify_bundle


def specimen(tmp_path):
    root = tmp_path / 'source'; root.mkdir()
    (root / 'one.csv').write_bytes(b'object,error\n1,-2.75\n')
    (root / 'duplicate.csv').write_bytes((root / 'one.csv').read_bytes())
    (root / 'camera.bmp').write_bytes(bytes(range(256)) * 8)
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps({'reviewed': True, 'files': [
        {'path': p.name, 'reason': 'original observations'} for p in root.iterdir()]}))
    output = tmp_path / 'bundle'
    manifest = pack(root, selection, output, 2500)
    return root, output, manifest


def test_saved_values_and_duplicate_paths_roundtrip_exactly(tmp_path):
    root, assets, manifest = specimen(tmp_path)
    assert manifest['paths'] == 3 and manifest['unique_objects'] == 2
    audit = verify_bundle(assets / 'RESEARCH_ASSETS.json.gz', assets, tmp_path / 'audit.json')
    assert audit['paths_verified'] == 3 and audit['unique_objects_read_and_sha256_verified'] == 2
    restored = tmp_path / 'restored'
    receipt = restore(assets / 'RESEARCH_ASSETS.json.gz', assets, restored)
    assert receipt['files_restored_and_verified'] == 3
    for original in root.iterdir():
        assert (restored / original.name).read_bytes() == original.read_bytes()
    with pytest.raises(FileExistsError):
        restore(assets / 'RESEARCH_ASSETS.json.gz', assets, restored)


def test_corrupted_asset_refused_before_any_restored_file(tmp_path):
    _, assets, manifest = specimen(tmp_path)
    (assets / manifest['assets'][0]['name']).write_bytes(b'broken archive')
    restored = tmp_path / 'restored'
    with pytest.raises(ValueError, match='asset changed'):
        restore(assets / 'RESEARCH_ASSETS.json.gz', assets, restored)
    assert not restored.exists()


def test_manifest_cannot_escape_restore_directory(tmp_path):
    _, assets, manifest = specimen(tmp_path)
    manifest['files'][0]['path'] = '../escape.csv'
    with gzip.open(assets / 'unsafe.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(manifest, stream)
    restored = tmp_path / 'restored'
    with pytest.raises(ValueError, match='Unsafe'):
        restore(assets / 'unsafe.json.gz', assets, restored)
    assert not restored.exists() and not (tmp_path / 'escape.csv').exists()


def test_clone_overlay_keeps_identical_files_and_refuses_changes(tmp_path):
    root, assets, manifest = specimen(tmp_path)
    clone = tmp_path / 'clone'; clone.mkdir()
    (clone / 'one.csv').write_bytes((root / 'one.csv').read_bytes())
    report = restore(assets / 'RESEARCH_ASSETS.json.gz', assets, clone, keep_identical_existing=True)
    assert report['identical_existing_files_reused'] == 1
    changed = tmp_path / 'changed-clone'; changed.mkdir()
    (changed / 'one.csv').write_bytes(b'user edit')
    with pytest.raises(FileExistsError, match='differs'):
        restore(assets / 'RESEARCH_ASSETS.json.gz', assets, changed, keep_identical_existing=True)
    assert list(changed.iterdir()) == [changed / 'one.csv']
