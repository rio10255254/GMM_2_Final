"""Reproducible execution and binary-only run records."""
from pathlib import Path
import os
import random
import hashlib
import numpy as np
import torch


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup(seed):
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def choose_device(request='auto'):
    if request == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    if request.startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable. Choose cpu or a CUDA-enabled Python environment.')
    return request


def save_checkpoint(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    torch.save(value, temporary)
    os.replace(temporary, path)


def save_metrics(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    numeric = sorted({k for r in rows for k, v in r.items() if isinstance(v, (int, float))})
    values = np.array([[r.get(k, np.nan) for k in numeric] for r in rows], dtype=np.float64)
    text = {k: np.array([str(r.get(k, '')) for r in rows]) for k in ('parent_id', 'category', 'phase')}
    with path.open('wb') as stream:
        np.savez_compressed(stream, columns=np.array(numeric), values=values, **text)


def save_assessment(path, result):
    with Path(path).open('wb') as stream:
        np.savez_compressed(stream, split=np.array(result['split']), parents=np.array(result['parents']),
                            names=np.array(list(result['mean'])), values=np.array(list(result['mean'].values()), np.float64))
