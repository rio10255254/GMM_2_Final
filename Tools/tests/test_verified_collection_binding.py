"""Actual restored bytes can pass while a historical image remains unreadable."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from bind_verified_collections_to_master import bind
from research_asset_bundle import pack, restore
from verify_model_archive_batch import inspect_data_format


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            json.dump(value, stream)
    else:
        path.write_text(json.dumps(value), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path):
    op = tmp_path / 'operation'
    for family in ['model', 'numeric', 'image', 'package']:
        save(op / (family + '_batches/PLAN.json'), {'tag': 'fixture-' + family, 'batches': []})
    source = tmp_path / 'source'
    source.mkdir()
    stream = io.BytesIO()
    np.save(stream, np.array([1.25, np.inf], dtype=np.float32))
    (source / 'original_values.npy').write_bytes(stream.getvalue())
    (source / 'historical_unreadable.bmp').write_bytes(b'original invalid camera-file fixture')
    selection = tmp_path / 'selection.json'
    save(selection, {'reviewed': True, 'files': [{'path': name, 'scope': 'fixture', 'reason': 'retain original failure'}
          for name in ['original_values.npy', 'historical_unreadable.bmp']]})
    folder = op / 'numeric_batches/B001'
    manifest = pack(source, selection, folder / 'bundle', 100_000)
    restored = tmp_path / 'restored'
    restore(folder / 'bundle/RESEARCH_ASSETS.json.gz', folder / 'bundle', restored)
    checks = []
    for row in manifest['files']:
        path = restored / row['path']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
        checks.append({'sha256': row['sha256'], 'bytes': row['bytes'],
                       'original_project_path': row['path'], 'exact_file_bytes_restored': True,
                       **inspect_data_format(path, row['path'])})
    receipt = folder / 'BATCH_GITHUB_RESTORE_VERIFIED.json'
    save(receipt, {'status': 'PASS_FILE_IDENTITY_AND_RESTORATION', 'checks': checks,
                   'assets': manifest['assets']})
    save(op / 'numeric_batches/PLAN.json', {'tag': 'fixture-numeric', 'batches': [{'batch': 'B001', 'folder': str(folder)}]})
    metadata = tmp_path / 'master'
    metadata.mkdir()
    component = metadata / 'NUMERIC.json.gz'
    for row in manifest['files']:
        row['scope'] = 'fixture'
    save(component, manifest)
    master = metadata / 'MASTER_RESTORE_INDEX.json'
    save(master, {'state': 'complete', 'components': [{'tag': 'fixture-numeric', 'new_collection': True,
                    'restore_manifest': component.name, 'manifest_sha256': sha(component)}],
                 'batch_checks': [{'tag': 'fixture-numeric', 'batch': 'B001', 'verification_sha256': sha(receipt)}]})
    return op, master, receipt


def test_bound_summary_preserves_actual_format_failure_without_claiming_array_validity(tmp_path):
    op, master, _ = fixture(tmp_path)
    output = tmp_path / 'bound'
    bind(op, master, output)
    result = json.loads((output / 'fixture-numeric/COLLECTION_VERIFICATION.json').read_text(encoding='utf-8'))
    batch = result['batch_receipts'][0]
    summary = batch['object_format_inspection']
    assert summary['format_status_counts'] == {'IMAGE_DECODE_FAILURE_PRESERVED': 1, 'NUMPY_HEADER_READABLE': 1}
    assert batch['unique_objects_checked'] == 2 and batch['original_load_errors_preserved'] == 0
    failure, = summary['recorded_format_failures']
    assert failure['inspection_representative_path'] == 'historical_unreadable.bmp'
    assert failure['sha256'] == hashlib.sha256(b'original invalid camera-file fixture').hexdigest()
    assert summary['numpy_header_readability_does_not_establish_all_values_finite']
    assert not any('all_tensors_finite' in row for row in result['batch_receipts'])
    with gzip.open(output / 'fixture-numeric/RESEARCH_ASSETS.json.gz', 'rt', encoding='utf-8') as stream:
        assert len(json.load(stream)['files']) == 2


def test_changed_restoration_receipt_refuses_binding_before_output(tmp_path):
    op, master, receipt = fixture(tmp_path)
    value = json.loads(receipt.read_text(encoding='utf-8'))
    value['checks'][1]['format_status'] = 'IMAGE_DECODED'
    save(receipt, value)
    output = tmp_path / 'must_not_approve'
    with pytest.raises(ValueError, match='receipt changed'):
        bind(op, master, output)
    assert not output.exists()
