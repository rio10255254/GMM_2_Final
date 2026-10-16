"""The original R152 recipe, with resume and an optional complete two-stage run."""
from copy import deepcopy
from pathlib import Path
import math
import signal
import time
import numpy as np
import torch

from settings import ROOT, BASE_MODEL_CONFIG, model_config
from models.r152_model import Model as R152
from models.base_model import Model as BaseModel
from .dataset import Bank
from .losses import objective as extension_objective
from .base_losses import objective as base_objective
from .runtime import setup, save_checkpoint, save_metrics, save_assessment


def lr_for(step, total, cfg):
    optimum = cfg['optimizer']
    warm = min(cfg['warmup'], max(8, total//8))
    if step <= warm:
        return optimum['max_lr']*step/warm
    return optimum['min_lr']+.5*(optimum['max_lr']-optimum['min_lr'])*(1+math.cos(math.pi*(step-warm)/(total-warm)))


def forward_loss(model, batch, cfg, phase):
    if phase == 'base':
        output, states = model(batch['source'], batch['operator_psf_indices'], return_states=True)
        loss, terms = base_objective(states, batch, model, cfg)
    else:
        output, parts = model(batch['source'], batch['operator_psf_indices'], return_parts=True)
        loss, terms = extension_objective(output, parts, batch, model, cfg)
    return loss, terms


def assess(model, bank, split, device, cfg, phase, limit=None):
    model.eval()
    count = cfg['splits'][split] if limit is None else min(limit, cfg['splits'][split])
    rows = []
    with torch.inference_mode():
        for index in range(count):
            batch = bank.batch(split, index, device)
            loss, terms = forward_loss(model, batch, cfg, phase)
            task = sum(cfg['loss'][k]*terms[k] for k in ('image', 'gradient', 'pair_output', 'boundary'))
            task = task + cfg['loss']['observation']*terms['observation']
            rows.append(dict(total=float(loss), task=float(task), **{k: float(v) for k, v in terms.items()}))
    return dict(split=split, parents=count, mean={k: sum(r[k] for r in rows)/count for k in rows[0]})


def train_phase(phase, cfg, output_dir, device, resume=None, max_updates=None, assessment_limit=None,
                base_checkpoint=None, finalized_step=False):
    cfg = deepcopy(cfg)
    cfg['device'] = device
    total = int(cfg['updates'])
    if total <= 0:
        raise ValueError('updates must be positive')
    setup(cfg['model_seed'])
    if phase == 'base':
        architecture = deepcopy(BASE_MODEL_CONFIG)
        model = BaseModel(architecture, ROOT).to(device)
    else:
        architecture = model_config() if resume is not None else model_config(base_checkpoint)
        model = R152(architecture, ROOT).to(device)
    trainable = [p for p in model.parameters() if p.requires_grad]
    if phase == 'extension' and sum(p.numel() for p in trainable) != 12699:
        raise ValueError('R152 trainable extension does not match the validated architecture')
    optimizer = torch.optim.AdamW(trainable, lr=cfg['optimizer']['max_lr'], weight_decay=cfg['optimizer']['weight_decay'])
    bank = Bank(cfg)
    directory = Path(output_dir)
    if directory.exists() and any(directory.iterdir()) and resume is None:
        raise FileExistsError('Output directory already contains a run. Use --resume or another output directory.')
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'checkpoints').mkdir(exist_ok=True)
    start = 0
    history = []
    if resume is not None:
        cp = torch.load(resume, map_location='cpu', weights_only=False)
        if cp.get('phase') != phase:
            raise ValueError('Resume checkpoint belongs to a different training phase')
        if cp.get('model_config') != architecture:
            raise ValueError('Resume architecture differs from settings.py')
        if int(cp.get('seed', cfg['model_seed'])) != cfg['model_seed']:
            raise ValueError('Resume seed differs from settings.py')
        saved_cfg = cp.get('train_config', {})
        for key in ('splits', 'views_per_parent', 'order_seed', 'noise_seed', 'operator_seed', 'loss',
                    'optimizer', 'warmup', 'known_operator_probability', 'supervised_core', 'observation_core'):
            if key in saved_cfg and saved_cfg[key] != cfg[key]:
                raise ValueError('Resume configuration changed: ' + key)
        if 'stage_weights' in saved_cfg and saved_cfg['stage_weights'] != cfg.get('stage_weights'):
            raise ValueError('Resume stage weights changed')
        model.load_state_dict(cp['model'], strict=True)
        optimizer.load_state_dict(cp['optimizer'])
        torch.set_rng_state(cp['torch_rng'])
        if device.startswith('cuda') and cp.get('cuda_rng'):
            torch.cuda.set_rng_state_all(cp['cuda_rng'])
        start = int(cp['step'])
        history = list(cp.get('history', []))
        if start >= total and not finalized_step:
            raise ValueError('The total update count must exceed the resumed update count')
    stop = total if max_updates is None else min(total, int(max_updates))
    if stop <= start and not (finalized_step and start == total):
        raise ValueError('--max-updates is a cumulative count and must exceed the resumed step')
    if start == 0:
        if phase == 'extension':
            model.set_deployment_scale(0)
            save_assessment(directory/'dev_base.npz', assess(model, bank, 'dev', device, cfg, phase, assessment_limit))
            model.set_deployment_scale(1)
        save_assessment(directory/'dev_initial.npz', assess(model, bank, 'dev', device, cfg, phase, assessment_limit))
    begin = time.perf_counter()
    def checkpoint(step, name='last.pth', final=False):
        saved_architecture = deepcopy(architecture)
        if phase == 'extension':
            saved_architecture = model_config()
        value = dict(model_name='R152' if phase == 'extension' else 'R152 base', phase=phase,
                     model={k: v.detach().cpu() for k, v in model.state_dict().items()},
                     optimizer=optimizer.state_dict(), step=step, seed=cfg['model_seed'],
                     model_config=saved_architecture, train_config=cfg, history=history,
                     torch_rng=torch.get_rng_state(),
                     cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                     checkpoint_kind='completed_short_test' if final and (total < 8192 or assessment_limit is not None)
                     else 'trained_extension' if final and phase == 'extension' else 'trained_base' if final else 'incomplete_training')
        save_checkpoint(directory/name, value)
        save_metrics(directory/'training_metrics.npz', history)
        return directory/name
    last_step = start
    stop_requested = False
    previous_handler = signal.getsignal(signal.SIGINT)
    def request_stop(_signal, _frame):
        nonlocal stop_requested
        stop_requested = True
    signal.signal(signal.SIGINT, request_stop)
    try:
        for step in range(start+1, stop+1):
            epoch = (step-1)//cfg['splits']['train']
            index = int(bank.order(epoch)[(step-1) % cfg['splits']['train']])
            batch = bank.batch('train', index, device, epoch)
            model.train()
            if phase == 'extension':
                model.set_deployment_scale(1)
            optimizer.zero_grad(set_to_none=True)
            loss, terms = forward_loss(model, batch, cfg, phase)
            loss.backward()
            gradient = float(torch.nn.utils.clip_grad_norm_(trainable, cfg['optimizer']['gradient_clip'], error_if_nonfinite=True))
            rate = lr_for(step, total, cfg)
            for group in optimizer.param_groups:
                group['lr'] = rate
            optimizer.step()
            row = dict(step=step, epoch=epoch, parent_id=batch['parent_id'], category=batch['category'],
                       phase=phase, loss=float(loss), gradient_l2=gradient, learning_rate=rate,
                       **{k: float(v) for k, v in terms.items()})
            if phase == 'extension':
                row.update(weight_min=float(model.psf_fusion.last_weights.min()),
                           weight_max=float(model.psf_fusion.last_weights.max()))
            history.append(row)
            last_step = step
            if step % 32 == 0 or step == stop:
                elapsed = time.perf_counter()-begin
                remaining = (total-step)*elapsed/max(1, step-start)
                print(f'{phase}: {step}/{total}  loss={float(loss):.8f}  elapsed={elapsed:.1f}s  ETA={remaining/3600:.2f}h', flush=True)
            if step % cfg['save_every'] == 0 or step == stop:
                checkpoint(step)
                checkpoint(step, f'checkpoints/step{step:05d}.pth')
            if step % cfg['dev_every'] == 0:
                save_assessment(directory/f'dev_{step:05d}.npz', assess(model, bank, 'dev', device, cfg, phase, assessment_limit))
            if stop_requested:
                checkpoint(step)
                print('Stopped after a complete update. Resume from', directory/'last.pth', flush=True)
                return dict(complete=False, step=step, checkpoint=directory/'last.pth')
    finally:
        signal.signal(signal.SIGINT, previous_handler)
    if last_step < total:
        return dict(complete=False, step=last_step, checkpoint=directory/'last.pth')
    if phase == 'extension':
        model.set_deployment_scale(0)
        base = assess(model, bank, 'dev', device, cfg, phase, assessment_limit)
        candidates = []
        for scale in cfg['deployment_scale_candidates']:
            model.set_deployment_scale(scale)
            result = assess(model, bank, 'dev', device, cfg, phase, assessment_limit)
            accepted = all(result['mean'][k] <= base['mean'][k]*(1+cfg['deployment_guard_relative'])
                           for k in ('image', 'gradient', 'pair_output', 'boundary', 'observation'))
            candidates.append(dict(scale=scale, accepted=accepted, result=result))
        chosen = min((x for x in candidates if x['accepted']), key=lambda x: x['result']['mean']['task'])
        model.set_deployment_scale(chosen['scale'])
        with (directory/'deployment_selection.npz').open('wb') as stream:
            np.savez_compressed(stream, scales=np.array([x['scale'] for x in candidates]),
                                accepted=np.array([x['accepted'] for x in candidates]),
                                task=np.array([x['result']['mean']['task'] for x in candidates]),
                                chosen_scale=np.array(chosen['scale']))
        final_path = checkpoint(total, 'deployed.pth', final=True)
    else:
        final_path = checkpoint(total, 'trained_base.pth', final=True)
    save_assessment(directory/'test_final.npz', assess(model, bank, 'test', device, cfg, phase, assessment_limit))
    print('FINISHED', phase, final_path, flush=True)
    return dict(complete=True, step=total, checkpoint=final_path)
