import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from download_research_assets import select_prefix_assets


def example():
    assets = [{'name': name, 'bytes': size, 'sha256': letter * 64}
              for name, size, letter in [('r93.zip', 100, 'a'), ('r94.zip', 200, 'b')]]
    manifest = {'state': 'complete', 'assets': assets, 'files': [
        {'path': 'Experiments/R93/data/a.npy', 'asset': 'r93.zip'},
        {'path': 'Experiments/R93/data/b.npy', 'asset': 'r93.zip'},
        {'path': 'Experiments/R930/data/c.npy', 'asset': 'r94.zip'},
    ]}
    remote = [{'name': a['name'], 'size': a['bytes'], 'digest': 'sha256:' + a['sha256']}
              for a in assets]
    return manifest, remote


def test_prefix_selects_whole_assets_and_respects_path_boundaries():
    manifest, remote = example()
    selected, count = select_prefix_assets(manifest, remote, ['Experiments/R93/'])
    assert [a['name'] for a in selected] == ['r93.zip']
    assert count == 2


def test_multiple_prefixes_do_not_duplicate_downloads():
    manifest, remote = example()
    selected, count = select_prefix_assets(manifest, remote,
                                          ['Experiments/R93', 'Experiments/R93/data/a.npy'])
    assert len(selected) == 1 and count == 2


@pytest.mark.parametrize('prefix', ['', '../outside', 'C:/outside', '/outside'])
def test_rejects_unsafe_prefixes(prefix):
    manifest, remote = example()
    with pytest.raises(ValueError):
        select_prefix_assets(manifest, remote, [prefix])


def test_missing_prefix_stops_without_selecting_the_whole_release():
    manifest, remote = example()
    with pytest.raises(ValueError, match='No research sources'):
        select_prefix_assets(manifest, remote, ['Experiments/Missing'])


@pytest.mark.parametrize('change', ['missing', 'digest', 'size', 'duplicate'])
def test_rejects_unverified_release_metadata(change):
    manifest, remote = example()
    remote = copy.deepcopy(remote)
    if change == 'missing':
        remote = remote[1:]
    elif change == 'digest':
        remote[0]['digest'] = 'sha256:' + 'f' * 64
    elif change == 'size':
        remote[0]['size'] += 1
    else:
        remote.append(copy.deepcopy(remote[0]))
    with pytest.raises(ValueError):
        select_prefix_assets(manifest, remote, ['Experiments/R93'])
