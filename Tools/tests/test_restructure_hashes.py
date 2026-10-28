"""Hash chain: a rewritten file's new sha256 replaces the old one wherever it is recorded, until nothing changes."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from restructure_hashes import NotConverging, propagate

H_A, H_A2, H_B = 'a' * 64, 'b' * 64, 'c' * 64


@pytest.fixture
def store():
    files = {}
    return files, files.__getitem__, files.__setitem__


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_chain_reaches_fixed_point(store):
    files, read, write = store
    files['index.json'] = json.dumps({'files': [{'path': 'a.md', 'sha256': H_A, 'bytes': 3}]}, indent=1).encode()
    files['top.json'] = json.dumps({'index': sha(files['index.json'])}).encode()
    rep = propagate({H_A: H_A2}, {H_A2: 7}, ['index.json', 'top.json'], read, write)
    assert json.loads(files['index.json'])['files'][0] == {'path': 'a.md', 'sha256': H_A2, 'bytes': 7}
    assert json.loads(files['top.json'])['index'] == sha(files['index.json'])
    assert rep.rounds == 2 and sorted(rep.touched_files) == ['index.json', 'top.json']


def test_only_exact_64hex_tokens(store):
    files, read, write = store
    files['notes.txt'] = ('x' + H_A + 'y\n' + H_A[:63] + '\n').encode()
    propagate({H_A: H_A2}, {}, ['notes.txt'], read, write)
    assert files['notes.txt'] == ('x' + H_A + 'y\n' + H_A[:63] + '\n').encode()


def test_size_updated_only_in_the_same_object(store):
    files, read, write = store
    files['m.json'] = b'{"bytes": 1, "rows": [{"sha256": "' + H_A.encode() + b'", "size": 3}, {"sha256": "' + H_B.encode() + b'", "size": 9}]}'
    propagate({H_A: H_A2}, {H_A2: 5}, ['m.json'], read, write)
    assert json.loads(files['m.json']) == {'bytes': 1, 'rows': [{'sha256': H_A2, 'size': 5}, {'sha256': H_B, 'size': 9}]}


def test_formatting_kept(store):
    files, read, write = store
    files['m.json'] = ('{\r\n  "sha256" : "' + H_A + '",\r\n  "bytes" : 3\r\n}\r\n').encode()
    propagate({H_A: H_A2}, {H_A2: 12}, ['m.json'], read, write)
    assert files['m.json'] == ('{\r\n  "sha256" : "' + H_A2 + '",\r\n  "bytes" : 12\r\n}\r\n').encode()


def test_csv_row_size_column(store):
    files, read, write = store
    files['r.csv'] = ('path,sha256,bytes\r\na.md,' + H_A + ',3\r\nb.md,' + H_B + ',4\r\n').encode()
    propagate({H_A: H_A2}, {H_A2: 8}, ['r.csv'], read, write)
    assert files['r.csv'] == ('path,sha256,bytes\r\na.md,' + H_A2 + ',8\r\nb.md,' + H_B + ',4\r\n').encode()


def test_json_gz(store):
    files, read, write = store
    files['m.json.gz'] = gzip.compress(json.dumps({'sha256': H_A, 'bytes': 3}).encode())
    propagate({H_A: H_A2}, {H_A2: 4}, ['m.json.gz'], read, write)
    assert json.loads(gzip.decompress(files['m.json.gz'])) == {'sha256': H_A2, 'bytes': 4}


def test_round_limit_is_reported(store):
    # two files can never hold each other's current sha, so a real cycle cannot occur; the limit is a safety net
    files, read, write = store
    files['p.txt'] = b'seed ' + H_A.encode() + b'\n'
    files['q.txt'] = b'p=' + sha(files['p.txt']).encode() + b'\n'
    with pytest.raises(NotConverging):
        propagate({H_A: H_A2}, {}, ['p.txt', 'q.txt'], read, write, max_rounds=1)


def test_large_manifest_is_fast(store):
    import time
    files, read, write = store
    rows = [{'path': f'f{i}', 'sha256': (H_A if i % 50 == 0 else format(i, '064x')), 'bytes': 1} for i in range(60000)]
    files['big.json'] = json.dumps({'files': rows}).encode()
    t0 = time.perf_counter()
    propagate({H_A: H_A2}, {H_A2: 2}, ['big.json'], read, write)
    out = json.loads(files['big.json'])['files']
    assert out[0] == {'path': 'f0', 'sha256': H_A2, 'bytes': 2} and out[1]['bytes'] == 1
    assert time.perf_counter() - t0 < 5
