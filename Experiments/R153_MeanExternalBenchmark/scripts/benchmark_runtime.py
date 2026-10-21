"""Fresh-process, fixed-frame FP32 runtime measurements; refuse concurrent training."""
from pathlib import Path
import argparse, datetime, gc, sys, time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import MOSR_SOURCE, read, save, sha
from scripts.monitor_training import processes
from inference_methods import RUNTIME_FRAME_NUMBERS


def selected_frames():
    frames = read(MOSR_SOURCE / 'evaluation/capture_plan.json')['frames']
    assert len(frames) == 930
    selected = [frames[i] for i in RUNTIME_FRAME_NUMBERS]
    for frame in selected:
        assert sha(frame['source']['path']) == frame['source']['sha256']
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True)
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    frames = selected_frames()
    if args.inspect:
        print({'method': args.method, 'frame_numbers': RUNTIME_FRAME_NUMBERS,
               'frames': [(f['run'], f['index']) for f in frames],
               'warmup': 2, 'repetitions': 5, 'precision': 'FP32', 'batch': 1})
        return
    managers, workers = processes()
    if managers or workers:
        raise RuntimeError('Training queue is active; defer isolated efficiency measurements until GPU is free')
    import cv2
    import numpy as np
    import torch
    from inference_methods import load_method, choose_mode, forward_with_mode
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, optics, checkpoint = load_method(args.method)
    print(args.method,'RUNTIME_MODEL_LOADED',flush=True)
    destination = ROOT / 'results/runtime' / (args.method + '.json')
    mode = None
    records = []
    with torch.inference_mode():
        for frame in frames:
            print(args.method,'RUNTIME_FRAME',frame['run'],frame['index'],flush=True)
            image = cv2.imread(frame['source']['path'], cv2.IMREAD_UNCHANGED)
            assert image.dtype == np.uint8 and image.shape == (1544, 2064)
            x = torch.from_numpy(image.astype(np.float32)[None, None] / 255).cuda()
            if mode is None:
                output, mode, fallback = choose_mode(args.method, model, optics, x)
                assert torch.isfinite(output).all() and output.shape == x.shape
                del output
                print(args.method,'RUNTIME_MODE',mode,flush=True)
                # A real reconstruction, if present, must use the same predeclared mode.
                real_mode = ROOT / 'results/reconstruction' / args.method / 'inference_mode.json'
                if real_mode.exists():
                    assert read(real_mode)['mode'] == mode, 'Runtime and real reconstruction modes differ'
            for _ in range(2):
                output = forward_with_mode(args.method, model, optics, x, mode)
                torch.cuda.synchronize()
                del output
            print(args.method,'RUNTIME_WARMUP_COMPLETE',flush=True)
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            samples = []
            for repetition in range(5):
                torch.cuda.reset_peak_memory_stats()
                allocated_start = torch.cuda.memory_allocated()
                torch.cuda.synchronize()
                start = time.perf_counter()
                output = forward_with_mode(args.method, model, optics, x, mode)
                torch.cuda.synchronize()
                seconds = time.perf_counter() - start
                peak_allocated = torch.cuda.max_memory_allocated()
                peak_reserved = torch.cuda.max_memory_reserved()
                assert output.dtype == torch.float32 and output.shape == x.shape and torch.isfinite(output).all()
                samples.append({'repetition': repetition + 1, 'forward_seconds': seconds,
                                'baseline_allocated_bytes': allocated_start,
                                'peak_allocated_bytes': peak_allocated,
                                'peak_reserved_bytes': peak_reserved})
                del output
                print(args.method,'RUNTIME_REPETITION',repetition+1,seconds,flush=True)
            records.append({'run': frame['run'], 'index': frame['index'],
                            'source_sha256': frame['source']['sha256'], 'samples': samples})
            del x
    save(destination, {'state': 'complete', 'method': args.method, 'checkpoint_sha256': checkpoint,
                       'measured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       'gpu': torch.cuda.get_device_name(), 'torch_version': torch.__version__,
                       'precision': 'FP32', 'TF32': False, 'batch': 1, 'warmup_per_frame': 2,
                       'repetitions_per_frame': 5, 'frames': records, 'mode': mode,
                       'memory_only_fallback': fallback, 'frame_numbers': RUNTIME_FRAME_NUMBERS,
                       'timing_scope': 'synchronized forward only; input transfer, image IO, output checks and readout excluded',
                       'memory_scope': 'current-process allocated and reserved peaks include model, optics, input and output; other processes excluded'})
    print(destination, flush=True)


if __name__ == '__main__':
    main()
