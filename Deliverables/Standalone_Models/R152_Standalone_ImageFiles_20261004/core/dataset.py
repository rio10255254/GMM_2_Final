"""Formal training reads clear/blur TIFF images and geometry TIFF labels."""
from functools import lru_cache
import ast
import hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import torch

from data_index import ENTRIES
from settings import ROOT, DATA_ROOT, resolve_path


class Bank:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = resolve_path(cfg['data_root']) if cfg.get('data_root') else DATA_ROOT
        entries = ENTRIES
        index_path = self.root/'data_index.py'
        if cfg.get('data_root') and index_path.is_file():
            tree = ast.parse(index_path.read_text(encoding='utf-8'), filename=str(index_path))
            assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'ENTRIES' for t in n.targets)]
            if len(assignments) != 1:
                raise ValueError('Generated data index is invalid')
            entries = ast.literal_eval(assignments[0].value)
            original = {(e['split'],e['index']):e for e in ENTRIES}
            if len(entries) != len(original):
                raise ValueError('Generated data is incomplete')
            for entry in entries:
                expected = original[(entry['split'],entry['index'])]
                for key in ('parent_id','category','metadata','array_sha256'):
                    if entry[key] != expected[key]:
                        raise ValueError('Generated data does not match R152: '+key)
                if len(entry['images']) != 4:
                    raise ValueError('Expected four generated views')
                for view in range(4):
                    for key in ('target','noiseless','sdf'):
                        if entry['images'][view][key] != expected['images'][view][key]:
                            raise ValueError('Generated image paths changed')
        self.entries = {(e['split'], e['index']): e for e in entries}
        if len(self.entries) != len(entries):
            raise ValueError('Duplicate training parents')
        for split, expected in cfg['splits'].items():
            if sum(k[0] == split for k in self.entries) != expected:
                raise ValueError('Wrong number of parents in ' + split)

    @lru_cache(maxsize=48)
    def read(self, split, index):
        entry = self.entries[(split, int(index))]
        gathered = {k: [] for k in ('target', 'noiseless', 'sdf')}
        for view in entry['images']:
            for key in gathered:
                path = self.root / Path(view[key]).relative_to('data')
                if hashlib.sha256(path.read_bytes()).hexdigest() != view[key+'_sha256']:
                    raise RuntimeError('Training image changed: '+str(path))
                with Image.open(path) as image:
                    values = np.asarray(image).copy()
                if values.dtype != np.float32 or values.ndim != 2:
                    raise ValueError('Expected the lossless grayscale TIFF image: '+str(path))
                gathered[key].append(values)
        arrays = {k: np.stack(v) for k, v in gathered.items()}
        dtype = {'valid': np.uint8, 'noise_sigma_gray': np.float64, 'psf_index': np.int64,
                 'shifts_xy': np.float64, 'contrast': np.float64, 'brightness_gray': np.float64}
        arrays.update({k: np.asarray(v, dtype=dtype[k]) for k, v in entry['metadata'].items()})
        return arrays, entry

    def order(self, epoch):
        return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'], epoch])).permutation(self.cfg['splits']['train'])

    def batch(self, split, index, device, epoch=None):
        arrays, entry = self.read(split, index)
        ep = 0 if epoch is None else int(epoch)
        observed = []
        for view in range(4):
            seed = np.random.SeedSequence([self.cfg['noise_seed'], {'train': 0, 'dev': 1, 'test': 2}[split], ep, int(index), view])
            rng = np.random.default_rng(seed)
            value = arrays['noiseless'][view].astype(np.float64) + rng.normal(0, arrays['noise_sigma_gray'][view]/255, arrays['noiseless'][view].shape)
            observed.append(np.rint(np.clip(value, 0, 1)*255).astype(np.uint8))
        x = np.ascontiguousarray(np.stack(observed)[:, None].astype(np.float32)/255)
        target = np.ascontiguousarray(arrays['target'][:, None])
        actual = np.where(arrays['psf_index'] < 0, -2, arrays['psf_index']).astype(np.int64)
        if split == 'train':
            rng = np.random.default_rng(np.random.SeedSequence([self.cfg['operator_seed'], ep, int(index)]))
            operator = actual.copy()
            operator[rng.random(4) >= self.cfg['known_operator_probability']] = -1
        else:
            operator = np.full_like(actual, -1)
        return {
            'source': torch.from_numpy(x).to(device), 'target': torch.from_numpy(target).to(device),
            'sdf': torch.from_numpy(arrays['sdf'][:, None]).to(device),
            'geometry_valid': torch.from_numpy(arrays['valid'].astype(bool)).to(device),
            'shifts_xy': torch.tensor(arrays['shifts_xy'], dtype=torch.float32, device=device),
            'actual_psf_indices': torch.from_numpy(actual).to(device),
            'operator_psf_indices': torch.from_numpy(operator).to(device),
            'core': (144, 240), 'observation_core': (160, 224),
            'parent_id': entry['parent_id'], 'category': entry['category'],
            'input_sha256': hashlib.sha256(x.tobytes(order='C')).hexdigest(), 'epoch': epoch,
        }
