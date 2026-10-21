"""Only an actually retrieved task-owned catalog may refresh frozen metadata."""
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hash_research_inventory_in_memory import checked_owned_catalog


def fixture(tmp_path):
    root=tmp_path/'source';op=tmp_path/'audit';op.mkdir()
    catalog=root/'docs/reproducibility/REPOSITORY_FILES.json.gz'
    catalog.parent.mkdir(parents=True);catalog.write_bytes(b'published catalog bytes')
    (op/'UPDATED_SOURCE_CONTEXT_DOWNLOAD_VERIFIED.json').write_text(json.dumps({
        'status':'PASS_ACTUAL_UPDATED_GITHUB_SOURCE_AND_CONTEXT_RETRIEVAL',
        'source_commit':'a'*40,'guard':'PASS'}),encoding='utf-8')
    return root,op,catalog


def test_only_exact_previously_retrieved_catalog_can_refresh(tmp_path):
    root,op,catalog=fixture(tmp_path)
    with patch('hash_research_inventory_in_memory.subprocess.check_output',return_value=catalog.read_bytes()):
        result=checked_owned_catalog(root,op,'a'*40)
    assert result['sha256']==hashlib.sha256(catalog.read_bytes()).hexdigest()
    assert result['path']=='docs/reproducibility/REPOSITORY_FILES.json.gz'


def test_unknown_source_commit_rejected_before_git(tmp_path):
    root,op,_=fixture(tmp_path)
    with patch('hash_research_inventory_in_memory.subprocess.check_output') as git:
        with pytest.raises(ValueError,match='isolated GitHub retrieval'):
            checked_owned_catalog(root,op,'b'*40)
        git.assert_not_called()


def test_changed_current_catalog_is_not_silently_accepted(tmp_path):
    root,op,catalog=fixture(tmp_path)
    published=catalog.read_bytes();catalog.write_bytes(b'changed source catalog')
    with patch('hash_research_inventory_in_memory.subprocess.check_output',return_value=published):
        with pytest.raises(ValueError,match='differs'):
            checked_owned_catalog(root,op,'a'*40)
    assert catalog.read_bytes()==b'changed source catalog'
