"""A recently changed research input must not hide behind an old source list."""
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_research_preservation_delta import compare_file


def record(path):
    info = path.stat()
    return {'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def test_changed_same_length_data_is_reported_and_original_is_retained(tmp_path):
    path = tmp_path / 'observations.csv'
    path.write_bytes(b'1,2,3\n')
    before = record(path)
    path.write_bytes(b'1,9,3\n')
    # Deliberately differ the metadata even on coarsely timed filesystems.
    before['mtime_ns'] -= 1000
    state, finding = compare_file(path, path.name, before, None)
    assert state == 'new_or_changed_research_content'
    assert finding['sha256'] != before['sha256']
    assert path.read_bytes() == b'1,9,3\n'


def test_new_document_already_in_frozen_source_catalog_is_not_a_data_gap(tmp_path):
    path = tmp_path / 'new_method.md'
    path.write_bytes(b'original source and result context\n')
    state, finding = compare_file(path, path.name, None, record(path))
    assert state == 'current_source_catalog_content' and finding is None
