"""Write the exact bounded R119 probe/formal command manifest."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = "python"


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, default=ROOT / 'reports/commands.json'); args = parser.parse_args()
    commands = []
    for candidate in ('A', 'B', 'D'):
        for seed in (1185001, 1185002):
            commands.append({'kind': 'probe', 'candidate': candidate, 'model_seed': seed, 'data_seed': 1196001, 'sampler_seed': 1197001, 'run_id': f'probe_{candidate}_s{seed}', 'argv': [PYTHON, 'training/train.py', '--mode', 'probe', '--candidate', candidate, '--run-id', f'probe_{candidate}_s{seed}', '--model-seed', str(seed), '--data-seed', '1196001', '--sampler-seed', '1197001', '--epochs', '12', '--limit', '512', '--batch', '8', '--workers', '2', '--device', 'cuda']})
    commands.append({'kind': 'formal_template', 'candidate': '<P09-selected>', 'model_seed': 1195001, 'data_seed': 1196001, 'sampler_seed': 1197001, 'run_id': 'formal_<P09-selected>_s1195001', 'argv': [PYTHON, 'training/train.py', '--mode', 'formal', '--candidate', '<P09-selected>', '--run-id', 'formal_<P09-selected>_s1195001', '--model-seed', '1195001', '--data-seed', '1196001', '--sampler-seed', '1197001', '--epochs', '42', '--limit', '0', '--batch', '12', '--workers', '4', '--device', 'cuda'], 'requires': 'P09 full_run_justified=true'} )
    result = {'schema_version': 1, 'plan_id': 'r118-next-single-image-sequence-geometry-v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'complete', 'probe_commands': commands[:-1], 'formal_template': commands[-1], 'same_step_budget': True, 'fresh_initialization': True, 'no_resume_argument': True, 'one_trainer_at_a_time': True, 'formal_not_authorized_by_this_file': True}
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps({'status': result['status'], 'probe_count': len(result['probe_commands']), 'formal_requires': result['formal_template']['requires']}, indent=2)); return 0


if __name__ == '__main__': raise SystemExit(main())
