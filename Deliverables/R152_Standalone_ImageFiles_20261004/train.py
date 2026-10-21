"""訓練入口：直接執行即開始正式R152擴充訓練。

完整重做兩階段：python train.py --from-scratch
使用重新生成的影像：python train.py --data-dir outputs/generated_data
續訓：python train.py --resume outputs/training/某次訓練/extension/last.pth
短暫檢查：python train.py --max-updates 2 --assessment-limit 1
設定和預設路徑集中在settings.py。只會寫入新訓練的輸出資料夾。
"""
import argparse
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import torch

from settings import OUTPUT_ROOT, DEFAULT_DEVICE, TRAIN_CONFIG, BASE_TRAIN_CONFIG, resolve_path
from core.runtime import choose_device
from core.training import train_phase


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from-scratch', action='store_true', help='先從零訓練主體，再訓練R152擴充')
    parser.add_argument('--resume', type=str, help='續訓的last.pth或訓練保存點')
    parser.add_argument('--output-dir', type=str, help='本次訓練輸出資料夾；預設包內outputs/training')
    parser.add_argument('--data-dir', type=str, help='重新生成的完整TIFF資料夾；預設使用附帶data')
    parser.add_argument('--device', default=DEFAULT_DEVICE, help='auto、cpu或cuda')
    parser.add_argument('--updates', type=int, help='累計更新總數；預設8192，續訓時必須大於已完成更新數')
    parser.add_argument('--max-updates', type=int, help='暫時停在這個累計更新數，不改正式總數與學習率排程')
    parser.add_argument('--assessment-limit', type=int, help='短測時限制開發／測試母場景數，正式使用不填')
    args = parser.parse_args(argv)
    device = choose_device(args.device)
    if args.assessment_limit is not None and args.assessment_limit <= 0:
        parser.error('--assessment-limit must be positive')
    resume = resolve_path(args.resume) if args.resume else None
    phase = 'base' if args.from_scratch else 'extension'
    if resume is not None:
        saved = torch.load(resume, map_location='cpu', weights_only=False)
        phase = saved.get('phase', 'extension')
        if phase not in ('base', 'extension'):
            raise ValueError('Unknown resume phase')
    if resume is not None and args.output_dir is None:
        phase_dir = resume.parent.parent if resume.parent.name == 'checkpoints' else resume.parent
        run_dir = phase_dir.parent
    else:
        run_dir = resolve_path(args.output_dir) if args.output_dir else OUTPUT_ROOT/'training'/datetime.now().strftime('run_%Y%m%d_%H%M%S_%f')
        phase_dir = run_dir/phase
    cfg = deepcopy(BASE_TRAIN_CONFIG if phase == 'base' else TRAIN_CONFIG)
    if args.data_dir is not None:
        cfg['data_root'] = str(resolve_path(args.data_dir))
    if args.updates is not None:
        cfg['updates'] = args.updates
    finish_pending_assessment = bool(resume is not None and int(saved['step']) == int(cfg['updates'])
                                     and saved.get('checkpoint_kind') == 'incomplete_training')
    print('R152 training', 'phase='+phase, 'device='+device, '\nOutput:', phase_dir, flush=True)
    result = train_phase(phase, cfg, phase_dir, device, resume=resume, max_updates=args.max_updates,
                         assessment_limit=args.assessment_limit, finalized_step=finish_pending_assessment)
    if phase == 'base' and result['complete']:
        extension_cfg = deepcopy(TRAIN_CONFIG)
        if args.data_dir is not None:
            extension_cfg['data_root'] = str(resolve_path(args.data_dir))
        if args.updates is not None:
            extension_cfg['updates'] = args.updates
        print('Base complete. Starting the R152 extension.', flush=True)
        result = train_phase('extension', extension_cfg, run_dir/'extension', device,
                             max_updates=args.max_updates, assessment_limit=args.assessment_limit,
                             base_checkpoint=Path(result['checkpoint']))
    print('Run complete.' if result['complete'] else 'Saved partial run; ready to resume.', '\nCheckpoint:', result['checkpoint'], flush=True)


if __name__ == '__main__':
    main()
