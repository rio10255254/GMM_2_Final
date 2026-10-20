"""A mismatched source clone must fail before large downloads or user writes."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('restore_master_client', TOOLS / 'restore_project_from_master.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


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
