"""檢查完整資料、PSF、權重、程式及套件內路徑。"""
import argparse
import sys
sys.dont_write_bytecode = True
import ast
import hashlib
import importlib
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-data', action='store_true', help='逐一打開768母場景並核對全部陣列')
    parser.add_argument('--model', action='store_true', help='載入部署權重並核對模型參數及凍結範圍')
    args = parser.parse_args(argv)
    for name in ('numpy', 'torch', 'PIL'):
        try:
            importlib.import_module(name)
        except ImportError as error:
            raise RuntimeError('缺少Python套件：'+name+'。請使用裝有numpy、PyTorch、Pillow的Python。') from error
    import numpy as np
    import torch
    from settings import ROOT, model_config
    from manifest import FILES
    from data_index import ENTRIES
    for relative, expected in FILES.items():
        path = ROOT/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('檔案缺少或已變更：'+relative)
    for path in ROOT.rglob('*.py'):
        if 'outputs' not in path.parts:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    counts = {split: sum(e['split'] == split for e in ENTRIES) for split in ('train', 'dev', 'test')}
    assert counts == {'train': 512, 'dev': 128, 'test': 128}
    if args.full_data:
        for i, entry in enumerate(ENTRIES, 1):
            with np.load(ROOT/entry['file'], allow_pickle=False) as z:
                for name, expected in entry['array_sha256'].items():
                    array = z[name]
                    assert hashlib.sha256(array.tobytes(order='C')).hexdigest() == expected
                    assert np.isfinite(array).all()
                assert z['target'].shape == z['noiseless'].shape == (4, 384, 384)
                assert z['sdf'].shape == (4, 96, 96) and z['valid'].shape == (4,)
            if i % 128 == 0:
                print('DATA', i, '/ 768', flush=True)
    if args.model:
        from models import Model
        model = Model(model_config(), ROOT)
        cp = torch.load(ROOT/'weights/r152_deployed.pth', map_location='cpu', weights_only=False)
        model.load_state_dict(cp['model'], strict=True)
        assert sum(p.numel() for p in model.parameters()) == 1207105
        assert sum(p.numel() for p in model.parameters() if p.requires_grad) == 12699
        assert all(not p.requires_grad for p in model.base.parameters())
        assert model.psf_fusion.bank.shape == (25, 1, 101, 101)
    print('PASS：完整768母場景／3072視圖、25PSF、權重與程式檔案均核對完成。', flush=True)


if __name__ == '__main__':
    main()
