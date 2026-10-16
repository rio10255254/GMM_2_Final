"""推論入口：直接執行會重建input資料夾的灰階影像。

python infer.py --input input --output outputs/inference
python infer.py --input 一張影像.bmp --weights weights/r152_deployed.pth
輸出包含原生float32 NPZ與十六位元PNG顯示圖。沒有額外銳化或尺寸校正。
"""
import argparse
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import time
import numpy as np
from PIL import Image
import torch

from settings import ROOT, INPUT_ROOT, OUTPUT_ROOT, DEFAULT_DEVICE, DEFAULT_WEIGHT, resolve_path, model_config
from models import Model
from core.runtime import choose_device, setup


def load_gray(path):
    with Image.open(path) as image:
        values = np.asarray(image)
        image_format = image.format
    if values.ndim != 2:
        raise ValueError('Expected a grayscale image: '+str(path))
    if values.dtype == np.uint8:
        return values.astype(np.float32)/255
    if values.dtype == np.uint16:
        return values.astype(np.float32)/65535
    if values.dtype == np.int32 and image_format == 'PNG' and values.min() >= 0 and values.max() <= 65535:
        return values.astype(np.float32)/65535
    raise ValueError('Expected 8-bit or 16-bit grayscale: '+str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=str, default=str(INPUT_ROOT))
    parser.add_argument('--output', type=str, default=str(OUTPUT_ROOT/'inference'))
    parser.add_argument('--weights', type=str, default=str(DEFAULT_WEIGHT))
    parser.add_argument('--device', default=DEFAULT_DEVICE)
    parser.add_argument('--untiled', action='store_true', help='整張執行；預設使用512/24的既定分塊')
    args = parser.parse_args(argv)
    setup(1309001)
    device = choose_device(args.device)
    source, output = resolve_path(args.input), resolve_path(args.output)
    weight_path = resolve_path(args.weights)
    checkpoint = torch.load(weight_path, map_location='cpu', weights_only=False)
    if checkpoint.get('phase') != 'extension':
        raise ValueError('Inference requires an R152 extension checkpoint')
    cfg = model_config()
    if checkpoint.get('model_config') != cfg:
        raise ValueError('Checkpoint architecture differs from settings.py')
    model = Model(cfg, ROOT).to(device).eval()
    model.load_state_dict(checkpoint['model'], strict=True)
    types = {'.bmp', '.png', '.tif', '.tiff', '.jpg', '.jpeg'}
    paths = [source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in types)
    if not paths:
        raise FileNotFoundError('No supported grayscale images in '+str(source))
    for i, path in enumerate(paths, 1):
        image = load_gray(path)
        x = torch.from_numpy(image[None, None]).to(device)
        if device.startswith('cuda'):
            torch.cuda.synchronize(torch.device(device))
            torch.cuda.reset_peak_memory_stats(torch.device(device))
        start = time.perf_counter()
        with torch.inference_mode():
            restored = model(x) if args.untiled else model.forward_tiled(x)
        if device.startswith('cuda'):
            torch.cuda.synchronize(torch.device(device))
        seconds = time.perf_counter()-start
        values = restored.cpu().numpy()[0, 0]
        if not np.isfinite(values).all():
            raise FloatingPointError('Nonfinite output for '+str(path))
        relative = path.relative_to(source) if source.is_dir() else Path(path.name)
        destination = output/relative.parent
        destination.mkdir(parents=True, exist_ok=True)
        with (destination/(path.stem+'_R152.npz')).open('wb') as stream:
            np.savez_compressed(stream, output=values, input_tensor_dtype=np.array(str(image.dtype)),
                                model=np.array('R152'), forward_seconds=np.array(seconds))
        preview = np.rint(values.astype(np.float64)*65535).clip(0, 65535).astype(np.uint16)
        Image.fromarray(preview).save(destination/(path.stem+'_R152.png'))
        print(f'[{i}/{len(paths)}] {path.name}: {seconds:.3f}s  -> {destination}', flush=True)


if __name__ == '__main__':
    main()
