"""Run the diagnostic-only untrained prototype on a file or folder."""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.calibration import load_observation
from model.network import build_model
from model.checkpoint import save_initialization, load_initialization
from inference.tiling import tiled_forward


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--profile', default=None)
    p.add_argument('--checkpoint')
    p.add_argument('--seed', type=int, default=1245001)
    p.add_argument('--core', type=int, default=256)
    p.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    args = p.parse_args()
    source, out = Path(args.input), Path(args.output)
    if out.exists():
        raise FileExistsError('Output folder must be new; source/evidence replacement is refused')
    files = [source] if source.is_file() else sorted(f for f in source.iterdir() if f.suffix.lower() in {'.bmp', '.png', '.tif', '.tiff'})
    if not files:
        raise ValueError('No input images')
    device = 'cuda' if args.device == 'auto' and torch.cuda.is_available() else 'cpu' if args.device == 'auto' else args.device
    torch.set_num_threads(2)
    if args.checkpoint:
        if args.profile:
            raise ValueError('Checkpoint already binds its observation; profile override is refused')
        model, payload = load_initialization(args.checkpoint, device)
        profile, seed = payload['observation_profile'], payload['seed']
    else:
        profile_path = Path(args.profile) if args.profile else ROOT/'config/identity_diagnostic.json'
        profile = json.loads(profile_path.read_text(encoding='utf-8-sig'))
        torch.manual_seed(args.seed)
        model = build_model(observation=load_observation(profile_path, device)).to(device).eval()
        seed = args.seed
    out.mkdir(parents=True, exist_ok=False)
    save_initialization(out/'initialization.pth', model, profile, seed)
    records = []
    for index, f in enumerate(files):
        digest = sha(f)
        raw = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if raw is None or raw.ndim != 2 or raw.dtype != np.uint8:
            raise ValueError(f'Prototype CLI requires grayscale uint8 camera units, got {f}')
        x = torch.from_numpy(raw.astype(np.float32)/255)[None, None].to(device)
        if device == 'cuda': torch.cuda.synchronize()
        start = time.perf_counter()
        y = tiled_forward(model, x, core=args.core)
        if device == 'cuda': torch.cuda.synchronize()
        result = y[0, 0].cpu().numpy()
        stem = f'{index:04d}_{f.stem}'
        np.savez_compressed(out/(stem+'.npz'), output=result)
        display = np.rint(result*255).clip(0, 255).astype(np.uint8)
        ok, encoded = cv2.imencode('.png', display)
        if not ok: raise RuntimeError('PNG encoding failed')
        encoded.tofile(str(out/(stem+'.png')))
        if sha(f) != digest: raise RuntimeError('Input changed during inference')
        records.append({'source': str(f.resolve()), 'source_sha256': digest,
                        'float_output': stem+'.npz', 'display_output': stem+'.png',
                        'shape': list(raw.shape), 'elapsed_seconds': time.perf_counter()-start,
                        'mean_absolute_change_gray': float(abs(result-raw/255).mean()*255),
                        'max_absolute_change_gray': float(abs(result-raw/255).max()*255)})
    metadata = {'status': 'untrained_engineering_outputs_only', 'training': False,
                'calibration_qualified': False, 'uncertainty_calibrated': False,
                'observation_profile': profile, 'seed': seed, 'core': args.core,
                'halo': model.required_halo, 'device': device, 'images': records,
                'interpretation': 'Modification is not evidence of improvement. No SEM label enters prediction.'}
    (out/'inference.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({'status': metadata['status'], 'images': len(records), 'output': str(out.resolve())}))


if __name__ == '__main__':
    main()
