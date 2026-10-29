"""Check the complete image-file training package, weights and Python entry points."""
import argparse
import ast
import hashlib
import importlib
import sys
sys.dont_write_bytecode = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-data', action='store_true', help='逐個打開完整TIFF訓練影像和標記')
    parser.add_argument('--model', action='store_true')
    args = parser.parse_args(argv)
    for name in ('numpy', 'torch', 'PIL', 'scipy'):
        try:
            importlib.import_module(name)
        except ImportError as error:
            raise RuntimeError('缺少Python套件：'+name) from error
    import numpy as np
    import torch
    from settings import ROOT, TRAIN_CONFIG, model_config
    from manifest import FILES
    from data_index import ENTRIES
    from core.dataset import Bank
    for relative, expected in FILES.items():
        path = ROOT/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('檔案缺少或變更：'+relative)
    for path in ROOT.rglob('*.py'):
        if 'outputs' not in path.parts:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    assert {split: sum(e['split'] == split for e in ENTRIES) for split in ('train','dev','test')} == {'train':512,'dev':128,'test':128}
    assert not list((ROOT/'data').rglob('*.npz'))
    assert not list((ROOT/'data').rglob('*.png'))
    from generation.source_history import SOURCES
    for source in SOURCES.values():
        assert hashlib.sha256((ROOT/source['delivered_path']).read_bytes()).hexdigest() == source['sha256']
    if args.full_data:
        bank = Bank(TRAIN_CONFIG)
        for i, entry in enumerate(ENTRIES,1):
            arrays, _ = bank.read(entry['split'], entry['index'])
            for key, expected in entry['array_sha256'].items():
                array = arrays[key]
                original = array.astype(np.float16) if key in ('target','noiseless','sdf') else array
                assert hashlib.sha256(original.tobytes(order='C')).hexdigest() == expected
                assert np.isfinite(array).all()
            assert arrays['target'].shape == arrays['noiseless'].shape == (4,384,384)
            assert arrays['sdf'].shape == (4,96,96)
            if i%128 == 0:
                print('IMAGE PARENTS',i,'/768',flush=True)
    if args.model:
        from models import Model
        model = Model(model_config(),ROOT)
        cp = torch.load(ROOT/'weights/r152_deployed.pth',map_location='cpu',weights_only=False)
        model.load_state_dict(cp['model'],strict=True)
        assert sum(p.numel() for p in model.parameters()) == 1207105
        assert sum(p.numel() for p in model.parameters() if p.requires_grad) == 12699
    print('PASS：獨立包與原始影像生成程式核對完成。',flush=True)
    if args.full_data:
        print('已實際打開並核對全部9216張TIFF。',flush=True)
    if args.model:
        print('已實際載入R152正式權重。',flush=True)


if __name__ == '__main__':
    main()
