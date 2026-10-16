"""Exercise actual shared-data references and preflight refusal of unsafe input."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restore_research_aliases import restore_aliases


def plan(tmp_path, rows):
    p = tmp_path / 'plan.json'
    p.write_text(json.dumps({'links': rows}), encoding='utf-8')
    return p


def test_actual_reference_reads_the_original_without_a_copy(tmp_path):
    root = tmp_path / 'workspace'; source = root / 'shared'; source.mkdir(parents=True)
    (source / 'measurement.csv').write_bytes(b'step,error\n1,-2.75\n')
    p = plan(tmp_path, [{'path': 'experiment/data', 'portable_target': 'shared', 'kind': 'inside_project'},
                        {'path': 'external-result', 'portable_target': None, 'kind': 'archived_output'}])
    receipt = restore_aliases(root, p, tmp_path / 'receipt.json')
    assert len(receipt['created']) == 1
    assert (root / 'experiment/data/measurement.csv').read_bytes() == (source / 'measurement.csv').read_bytes()
    assert (root / 'experiment/data').resolve() == source.resolve()
    assert not (root / 'external-result').exists()


def test_existing_folder_is_preserved_before_creating_other_aliases(tmp_path):
    root = tmp_path / 'workspace'; (root / 'shared').mkdir(parents=True)
    (root / 'user-data').mkdir(); (root / 'user-data/keep.txt').write_text('user content')
    p = plan(tmp_path, [{'path': 'new-alias', 'portable_target': 'shared', 'kind': 'inside_project'},
                        {'path': 'user-data', 'portable_target': 'shared', 'kind': 'inside_project'}])
    with pytest.raises(FileExistsError):
        restore_aliases(root, p, tmp_path / 'receipt.json')
    assert not (root / 'new-alias').exists()
    assert (root / 'user-data/keep.txt').read_text() == 'user content'


def test_target_cannot_escape_workspace(tmp_path):
    root = tmp_path / 'workspace'; root.mkdir(); (tmp_path / 'outside').mkdir()
    p = plan(tmp_path, [{'path': 'data', 'portable_target': '../outside', 'kind': 'inside_project'}])
    with pytest.raises(ValueError):
        restore_aliases(root, p, tmp_path / 'receipt.json')
    assert not (root / 'data').exists()


def test_complete_identical_package_is_reused_without_replacing_files(tmp_path):
    root = tmp_path / 'workspace'; (root / 'shared').mkdir(parents=True)
    (root / 'copy').mkdir()
    for name in ['shared', 'copy']:
        (root / name / 'geometry.csv').write_bytes(b'x,y\n2.5,4.0\n')
    p = plan(tmp_path, [{'path': 'copy', 'portable_target': 'shared', 'kind': 'inside_project'}])
    receipt = restore_aliases(root, p, tmp_path / 'receipt.json')
    assert not receipt['created'] and len(receipt['already_identical_directory']) == 1
    assert (root / 'copy').resolve() != (root / 'shared').resolve()
