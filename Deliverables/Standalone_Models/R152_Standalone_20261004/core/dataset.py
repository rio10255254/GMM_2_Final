"""Read the complete package-local four-view pairs and geometry."""
from functools import lru_cache
import hashlib
import numpy as np
import torch

from data_index import ENTRIES
from settings import DATA_ROOT


class Bank:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = DATA_ROOT
        self.entries = {(e['split'], e['index']): e for e in ENTRIES}
        for split, expected in cfg['splits'].items():
            if sum(k[0] == split for k in self.entries) != expected:
                raise ValueError('Wrong number of parents in ' + split)

    @lru_cache(maxsize=48)
    def read(self, split, index):
        entry = self.entries[(split, int(index))]
        path = self.root / split / f'{int(index):04d}.npz'
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError('Training item changed: ' + str(path))
        with np.load(path, allow_pickle=False) as archive:
            arrays = {k: archive[k].copy() for k in archive.files}
        return arrays, entry

    def order(self, epoch):
        return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'], epoch])).permutation(self.cfg['splits']['train'])

    def batch(self, split, index, device, epoch=None):
        arrays, entry = self.read(split, index)
        ep = 0 if epoch is None else int(epoch)
        noiseless = arrays['noiseless'].astype(np.float32)
        observed = []
        for view in range(4):
            seed = np.random.SeedSequence([self.cfg['noise_seed'], {'train': 0, 'dev': 1, 'test': 2}[split], ep, int(index), view])
            rng = np.random.default_rng(seed)
            value = noiseless[view].astype(np.float64) + rng.normal(0, arrays['noise_sigma_gray'][view]/255, noiseless[view].shape)
            observed.append(np.rint(np.clip(value, 0, 1)*255).astype(np.uint8))
        x = np.ascontiguousarray(np.stack(observed)[:, None].astype(np.float32)/255)
        target = np.ascontiguousarray(arrays['target'].astype(np.float32)[:, None])
        actual = np.where(arrays['psf_index'] < 0, -2, arrays['psf_index']).astype(np.int64)
        if split == 'train':
            rng = np.random.default_rng(np.random.SeedSequence([self.cfg['operator_seed'], ep, int(index)]))
            operator = actual.copy()
            operator[rng.random(4) >= self.cfg['known_operator_probability']] = -1
        else:
            operator = np.full_like(actual, -1)
        return {
            'source': torch.from_numpy(x).to(device),
            'target': torch.from_numpy(target).to(device),
            'sdf': torch.from_numpy(arrays['sdf'].astype(np.float32)[:, None]).to(device),
            'geometry_valid': torch.from_numpy(arrays['valid'].astype(bool)).to(device),
            'shifts_xy': torch.tensor(arrays['shifts_xy'], dtype=torch.float32, device=device),
            'actual_psf_indices': torch.from_numpy(actual).to(device),
            'operator_psf_indices': torch.from_numpy(operator).to(device),
            'core': (144, 240), 'observation_core': (160, 224),
            'parent_id': entry['parent_id'], 'category': entry['category'],
            'input_sha256': hashlib.sha256(x.tobytes(order='C')).hexdigest(), 'epoch': epoch,
        }
