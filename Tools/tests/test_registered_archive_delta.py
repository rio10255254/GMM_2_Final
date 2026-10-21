"""Current H checks stay bounded and detect new, changed and missing inputs."""
import hashlib
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_registered_archive_delta import inspect_roots,key,scoped_roots


def record(path,logical):
    info=path.stat()
    return {'source':str(path),'logical_path':logical,'bytes':info.st_size,
            'mtime_ns':info.st_mtime_ns,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'kind':'result_numeric'}


def test_roots_never_include_staging_or_the_whole_archive(tmp_path):
    archive=tmp_path/'archive';op=archive/'reproducibility/current';op.mkdir(parents=True)
    for target in [archive,archive/'reproducibility',op]:
        edges=[{'source':str(target),'target':str(target),'logical_path':'data'}]
        with pytest.raises(ValueError,match='staging or the whole archive'):
            scoped_roots(edges,archive,op)


def test_overlapping_registered_roots_are_visited_once(tmp_path):
    archive=tmp_path/'archive';parent=archive/'active/results';child=parent/'centers';child.mkdir(parents=True)
    op=archive/'reproducibility/current';op.mkdir(parents=True)
    edges=[{'source':str(path),'target':str(path),'logical_path':path.name} for path in [parent,child]]
    assert scoped_roots(edges,archive,op)==[parent]


def test_new_changed_and_missing_files_are_reported_without_source_changes(tmp_path):
    root=tmp_path/'registered';root.mkdir()
    unchanged=root/'same.csv';unchanged.write_bytes(b'1,2\n')
    changed=root/'changed.csv';changed.write_bytes(b'1,2\n')
    missing=root/'gone.csv';missing.write_bytes(b'1,2\n')
    baseline={key(path):record(path,'data/'+path.name) for path in [unchanged,changed,missing]}
    baseline[key(changed)]['mtime_ns']-=1000
    changed.write_bytes(b'1,9\n');missing.unlink()
    new=root/'new.csv';new.write_bytes(b'3,4\n')
    edges=[{'source':str(root),'target':str(root),'logical_path':'data'}]
    result=inspect_roots([root],baseline,edges,{}, {'excluded_path_prefixes':[],'excluded_content_objects':[]})
    assert result['file_states']['unchanged_since_full_content_audit']==1
    assert {row['path'] for row in result['new_changed_or_missing_contents']}=={
        'data/changed.csv','data/gone.csv','data/new.csv'}
    assert changed.read_bytes()==b'1,9\n' and new.read_bytes()==b'3,4\n'
    assert not missing.exists() and not result['read_or_reference_errors']
