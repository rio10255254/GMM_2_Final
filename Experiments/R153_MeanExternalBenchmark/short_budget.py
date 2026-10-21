"""Explicit user-authorized duration change; frozen losses/data/architecture retained."""
import copy, os, shutil, time
from study import ROOT, read, save, sha


def finalize_saved(method):
    import torch
    from normal_protocol import NORMAL
    from benchmark_models import make_model
    from benchmark_core import prepare, evaluate
    out = ROOT / 'runs' / method
    last = torch.load(out / 'last.pth', map_location='cpu', weights_only=False)
    best = torch.load(out / 'best_validation.pth', map_location='cpu', weights_only=False)
    assert last['method'] == best['method'] == method
    assert last['signature'] == best['signature']
    signature = last['signature']
    for field, filename in [('factory_sha256', 'benchmark_models.py'), ('normal_training_sha256', 'normal_training.py'), ('normal_data_sha256', 'normal_data.py')]:
        assert signature[field] == sha(ROOT / filename)
    assert last['completed_epochs'] >= 8
    assert last['best_epoch'] == best['selected_epoch']
    assert max(last['dev'][1:], key=lambda x: x['mean_PSNR_dB'])['epoch'] == best['selected_epoch']
    start = time.perf_counter()
    cfg, bank, optics = prepare()
    model = make_model(method, checkpoint_training=False).cuda().eval()
    model.load_state_dict(best['model'], strict=True)
    shutil.copy2(out / 'best_validation.pth', out / 'selected.pth')
    save(out / 'status.json', {'state': 'synthetic_test', 'method': method, 'pid': os.getpid(),
        'step': last['step'], 'epochs_completed': last['completed_epochs'],
        'selected_epoch': best['selected_epoch'], 'duration_revision': read(ROOT / 'config/TIME_BUDGET_OVERRIDE.json')})
    test = evaluate(model, bank, optics, 'test', with_image_metrics=True)
    save(out / 'synthetic_test.json', test)
    done = {'state': 'complete', 'method': method, 'epochs_trained': last['completed_epochs'],
        'updates': last['step'], 'partial_epoch_saved_updates': last['step'] - 512 * last['completed_epochs'],
        'selected_epoch': best['selected_epoch'], 'selected_step': best['selected_step'],
        'stopping_reason': 'user_authorized_short_budget_stop_using_saved_best',
        'validation_PSNR_dB': best['validation_PSNR_dB'], 'checkpoint': 'selected.pth',
        'checkpoint_sha256': sha(out / 'selected.pth'), 'total_parameters': sum(p.numel() for p in model.parameters()),
        'training_recipe': NORMAL[method], 'common_validation_protocol': signature['common'],
        'synthetic_test': test['mean'], 'real_data_used_in_training_or_selection': False,
        'elapsed_this_process_seconds': time.perf_counter() - start,
        'duration_revision': read(ROOT / 'config/TIME_BUDGET_OVERRIDE.json'),
        'interruption_record': 'runs/launcher_logs/time_budget_change/change.json',
        'notes': 'Complete epochs and saved partial updates reported separately; incomplete epoch not validated or selected; later unsaved updates are not used. Original checkpoints/history archived.'}
    save(out / 'training_complete.json', done)
    save(out / 'status.json', done)
    print('TRAINING_COMPLETE', method, 'epochs', done['epochs_trained'], 'selected', done['selected_epoch'], 'user_short_budget', flush=True)
    return done


def main():
    import argparse
    import normal_training
    parser = argparse.ArgumentParser()
    parser.add_argument('method')
    parser.add_argument('--output-dir')
    parser.add_argument('--max-updates', type=int)
    parser.add_argument('--assessment-limit', type=int)
    args = parser.parse_args()
    config = read(ROOT / 'config/TIME_BUDGET_OVERRIDE.json')
    assert config['user_authorized'] is True
    formal = args.max_updates is None and args.assessment_limit is None and args.output_dir is None
    if formal and args.method == config['finalize_saved_method']:
        if (ROOT / 'runs' / args.method / 'training_complete.json').exists():
            return read(ROOT / 'runs' / args.method / 'training_complete.json')
        return finalize_saved(args.method)
    if args.method in config['affected_methods']:
        normal_training.COMMON = copy.deepcopy(normal_training.COMMON)
        normal_training.COMMON['max_epochs'] = config['max_epochs']
        normal_training.COMMON['stopping'] = 'user-authorized shorter comparison: maximum 8 epochs; unchanged synthetic validation and selection'
    result = normal_training.run(args.method, args.output_dir or ROOT / 'runs' / args.method,
                                args.max_updates, args.assessment_limit)
    if formal and result is not None:
        result['duration_revision'] = config
        result['short_budget_entry_sha256'] = sha(__file__)
        save(ROOT / 'runs' / args.method / 'training_complete.json', result)
    return result
