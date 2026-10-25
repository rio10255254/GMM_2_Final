"""A local file counts as in the cloud only when identical bytes are there."""
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cloud_locator


def make_cloud(tmp_path, tree, releases):
    cloud=cloud_locator.Cloud.__new__(cloud_locator.Cloud)
    cloud.db=cloud_locator.open_index(tmp_path,create=True)
    cloud.db.executemany('INSERT INTO objects VALUES (?,?,?,?,?,?)',releases)
    cloud.git_ref='main'
    cloud.tree=tree
    cloud.blobs=set(tree.values())
    cloud.history_blobs={}
    return cloud


def test_hash_matches_git_blob_id_and_is_cached(tmp_path):
    db=cloud_locator.open_hashes(tmp_path/'cache')
    path=tmp_path/'result.csv'
    path.write_bytes(b'step,nm\r\n1,4.865\r\n')
    sha,blob=cloud_locator.hash_file(db,str(path),'result.csv',os.stat(path))
    expected=subprocess.run(['git','hash-object','--no-filters',str(path)],capture_output=True,text=True,check=True).stdout.strip()
    assert blob==expected
    assert db.execute('SELECT sha256 FROM hashes WHERE path=?',('result.csv',)).fetchone()[0]==sha


def test_same_path_needs_same_bytes(tmp_path):
    cloud=make_cloud(tmp_path,{'a/model.onnx':'blob1'},[('r/table.csv','sha-r','10','tag','part-01.zip','results')])
    assert cloud.classify('a/model.onnx',1,'x','blob1')[0]=='git'
    assert cloud.classify('a/model.onnx',1,'x','blob2')[0]=='changed'
    assert cloud.classify('r/table.csv',10,'sha-r',None)==('release','tag / part-01.zip')
    assert cloud.classify('r/table.csv',10,'other',None)[0]=='changed'


def test_moved_copies_are_found_by_content_and_unknown_files_stay_local(tmp_path):
    cloud=make_cloud(tmp_path,{'kept/copy.py':'blob1'},[('old/place.npz','sha-n',5,'tag','part-02.zip','models')])
    assert cloud.classify('new/copy.py',1,'x','blob1')[0]=='git-other-path'
    assert cloud.classify('new/place.npz',5,'sha-n','none')[0]=='release-other-path'
    assert cloud.classify('only/here.bmp',5,'sha-z','none')==('local-only','')


def test_files_removed_from_the_tree_count_as_recoverable_history(tmp_path):
    cloud=make_cloud(tmp_path,{},[])
    cloud.history_blobs={'blob-old':'Experiments/R33/results/recon/frame.bmp'}
    status,where=cloud.classify('Experiments/R33/results/recon/frame.bmp',3,'sha-b','blob-old')
    assert status=='git-history' and 'frame.bmp' in where
