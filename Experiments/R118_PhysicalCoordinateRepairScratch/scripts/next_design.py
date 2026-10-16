"""Read-only evidence/dependency checker. It cannot launch scientific work."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'reports/next_design_plan.json'
ASSETS = ROOT / 'reports/next_design_assets.json'
HASH_RE = re.compile(r'^[0-9a-f]{64}$')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def contained_path(root, relative):
    """Reject absolute paths, traversal, and symlinks escaping the work root."""
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError('empty or non-string artifact path')
    rel = Path(relative)
    if rel.is_absolute() or rel.drive or '..' in rel.parts:
        raise ValueError(f'unsafe relative path: {relative}')
    base = Path(root).resolve()
    result = (base / rel).resolve()
    if not result.is_relative_to(base) or result == base:
        raise ValueError(f'artifact escapes root: {relative}')
    return result


def verify_files(entries):
    errors = []
    seen = set()
    for entry in entries:
        path = Path(entry['path'])
        key = str(path.resolve()).casefold()
        if key in seen:
            errors.append(f'duplicate protected path: {path}')
        seen.add(key)
        expected = entry.get('sha256', '')
        if not HASH_RE.fullmatch(expected):
            errors.append(f'invalid recorded checksum: {path}')
        elif not path.is_file():
            errors.append(f'missing protected file: {path}')
        elif sha256(path) != expected:
            errors.append(f'changed protected file: {path}')
        elif entry.get('bytes') is not None and path.stat().st_size != entry['bytes']:
            errors.append(f'changed protected size: {path}')
    return errors


def validate_plan(plan):
    errors = []
    phases = plan.get('phases', [])
    if [p.get('id') for p in phases] != [f'P{i:02}' for i in range(13)]:
        errors.append('phase inventory must be exactly P00..P12 in order')
    seen = set()
    for phase in phases:
        if not set(phase.get('depends_on', [])).issubset(seen):
            errors.append(f'{phase.get("id")}: missing/forward/cyclic dependency')
        seen.add(phase.get('id'))
        for key in ('required_artifacts', 'required_checks'):
            values = phase.get(key, [])
            if len(values) != len(set(values)):
                errors.append(f'{phase.get("id")}: duplicate {key}')
    if plan.get('readonly_helper') is not True:
        errors.append('handoff helper must remain read-only')
    return errors


def verify_selection(selection, records, manifest_hash):
    errors = []
    if selection.get('base_manifest_sha256') != manifest_hash:
        errors.append('frozen ID selection uses another base manifest')
    by_id = {r['scene_index']: r for r in records}
    keys = [('probe_scene_ids', 512, 'train'), ('development_bank_scene_ids', 48, 'validation'),
            ('short_sequence_enrichment_ids', 96, 'train'), ('full_sequence_enrichment_ids', 960, 'train')]
    for key, count, split in keys:
        ids = selection.get(key, [])
        if len(ids) != count or len(set(ids)) != count:
            errors.append(f'{key}: wrong count or duplicate IDs')
        if any(i not in by_id or by_id[i]['split'] != split for i in ids):
            errors.append(f'{key}: unknown ID or wrong population')
        if key != 'probe_scene_ids':
            eligible = [by_id[i] for i in ids if i in by_id]
            if any(r['role'] == 'flat_negative' for r in eligible):
                errors.append(f'{key}: flat_negative is not a motion-bank geometry')
            strata = Counter((r['family'], r['polarity']) for r in eligible)
            if len(strata) != 24 or any(n != count // 24 for n in strata.values()):
                errors.append(f'{key}: family/polarity strata differ from the frozen design')
    probe = selection.get('probe_scene_ids', [])
    expected_probe = sorted(r['scene_index'] for r in records if r['split'] == 'train')[:512]
    if probe != expected_probe:
        errors.append('probe IDs are not the first 512 training scenes')
    if not set(selection.get('short_sequence_enrichment_ids', [])).issubset(probe):
        errors.append('short enrichment is not nested in the probe')
    if not set(selection.get('short_sequence_enrichment_ids', [])).issubset(selection.get('full_sequence_enrichment_ids', [])):
        errors.append('short enrichment is not nested in full enrichment')
    if set(probe) & set(selection.get('development_bank_scene_ids', [])):
        errors.append('training/development selected IDs overlap')
    return errors


def inspect_live(base_root, work_root):
    info = {'training_processes': [], 'warnings': []}
    for drive in ('D:/', 'H:/'):
        if Path(drive).exists():
            info[f'{drive[0]}_free_gib'] = round(shutil.disk_usage(drive).free / 2**30, 3)
    if sys.platform != 'win32':
        info['warnings'].append('Windows process inventory unavailable on this platform')
        return info
    command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' } "
               "| Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        processes = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(processes, dict):
            processes = [processes]
        roots = [str(p).replace('\\', '/').casefold() for p in (base_root, work_root)]
        for proc in processes:
            cmd = (proc.get('CommandLine') or '').replace('\\', '/').casefold()
            if any(root in cmd for root in roots) and re.search(r'(?:/|\s)train\.py(?:\s|"|$)', cmd):
                info['training_processes'].append(proc)
        info['warnings'].append('Process matching is command-line based; check markers/child tree before a launch.')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        info['warnings'].append(f'Process inventory unavailable: {exc}')
    gpu = shutil.which('nvidia-smi')
    if gpu:
        try:
            result = subprocess.run([gpu, '--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu',
                                     '--format=csv'], capture_output=True, text=True, timeout=15)
            info['gpu_snapshot'] = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            info['warnings'].append(f'GPU snapshot unavailable: {exc}')
    return info


def audit(root=ROOT, live=True):
    root = Path(root)
    plan = read_json(root / 'reports/next_design_plan.json')
    assets = read_json(root / 'reports/next_design_assets.json')
    errors = validate_plan(plan) + verify_files(assets['protected_files'])
    local_integrity = [{'path': str(contained_path(root, item['path'])), 'sha256': item['sha256']}
                       for item in plan.get('handoff_integrity', [])]
    errors.extend(verify_files(local_integrity))
    warnings = list(assets.get('known_limits', []))
    for executable in assets['required_executables']:
        if not Path(executable).is_file():
            errors.append(f'missing required executable: {executable}')
    for relative in ['NEXT_STEPS.md', *plan['documents']]:
        if not contained_path(root, relative).is_file():
            errors.append(f'missing handoff document: {relative}')
    observed = {}
    try:
        ready = read_json(root / assets['ready_file'])
        if ready.get('formal_training_started') is not False or ready.get('model_promoted') is not False:
            errors.append('R118 formal/promotion status changed; refresh the scientific handoff')
        if ready.get('checkpoint_sha256') != assets['expected_checkpoint_sha256']:
            errors.append('READY checkpoint does not match the protected reference')
        manifest = read_json(root / assets['data_manifest'])
        records = manifest['records']
        selection = read_json(root / 'reports/next_design_selected_ids.json')
        errors.extend(verify_selection(selection, records, sha256(root / assets['data_manifest'])))
        observed['frozen_selection_counts'] = {key: len(selection[key]) for key in
            ('probe_scene_ids', 'development_bank_scene_ids', 'short_sequence_enrichment_ids', 'full_sequence_enrichment_ids')}
        observed['data_counts'] = dict(Counter(r['split'] for r in records))
        if observed['data_counts'] != assets['expected_data_counts']:
            errors.append('base train/development counts changed')
        ids = [r['scene_index'] for r in records]
        if len(set(ids)) != len(ids):
            errors.append('duplicate base scene IDs')
        data_seeds = {r['seed'] for r in records}
        seal_path = root / assets['confirmation_manifest']
        seal = read_json(seal_path)
        if (seal.get('status') != 'sealed_not_evaluated' or seal.get('model_predictions_generated') is not False
                or seal.get('training_inclusion') is not False):
            errors.append('confirmation declaration changed; do not treat it as unseen')
        expected_count = assets['expected_confirmation_count']
        if seal.get('count') != expected_count or len(seal.get('records', [])) != expected_count:
            errors.append('confirmation inventory is not the expected 144')
        confirmation_files = []
        for record in seal.get('records', []):
            if record['seed'] in data_seeds:
                errors.append('confirmation seed overlaps base population')
            for file_key, hash_key in [('file', 'sha256'), ('geometry_file', 'geometry_sha256')]:
                path = contained_path(seal_path.parent, record[file_key])
                confirmation_files.append({'path': str(path), 'sha256': record[hash_key]})
        errors.extend(verify_files(confirmation_files))
        observed['confirmation_files_hashed_without_decoding'] = len(confirmation_files)
        observed['confirmation_status_is_manifest_declaration_only'] = True
    except (OSError, KeyError, ValueError, TypeError) as exc:
        errors.append(f'metadata validation failed: {exc}')
    work_root = Path(plan['proposed_work_root'])
    observed['proposed_work_root_exists'] = work_root.exists()
    consumed = work_root / 'results/confirmation/consumption.json'
    if consumed.exists():
        warnings.append('Confirmation consumption ledger exists in next work root. Source seal is historical, not permission to reuse.')
    live_info = inspect_live(root, work_root) if live else {'not_requested': True}
    if live_info.get('training_processes'):
        warnings.append('A matching trainer exists. Never launch a second trainer; inspect exact run identity.')
    return {'schema_version': 1, 'status': 'pass' if not errors else 'blocked',
            'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'plan_id': plan['plan_id'], 'plan_sha256': sha256(root / 'reports/next_design_plan.json'),
            'input_snapshot_sha256': sha256(root / 'reports/next_design_assets.json'),
            'protected_file_count': len(assets['protected_files']), 'errors': errors,
            'warnings': warnings, 'observed': observed, 'live': live_info,
            'meaning': 'Input integrity only. No next design implementation or training is certified.'}


def verify_receipt(phase, receipt_path, plan, plan_hash, snapshot_hash, work_root, dependency_hashes):
    errors = []
    try:
        receipt = read_json(receipt_path)
        for key, value in {'schema_version': 1, 'plan_id': plan['plan_id'], 'phase': phase['id'],
                           'status': 'complete', 'plan_sha256': plan_hash,
                           'input_snapshot_sha256': snapshot_hash}.items():
            if receipt.get(key) != value:
                errors.append(f'receipt {key} mismatch')
        stamp = datetime.fromisoformat(receipt['completed_at_utc'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            errors.append('completion timestamp must be UTC')
        if stamp > datetime.now(timezone.utc):
            errors.append('completion timestamp is in the future')
        expected_deps = {key: dependency_hashes[key] for key in phase['depends_on'] if key != 'P00'}
        if receipt.get('depends_on_receipts', {}) != expected_deps:
            errors.append('dependency receipt hashes missing or stale')
        entries = []
        artifact_names = set()
        for artifact in receipt.get('artifacts', []):
            relative = artifact['path']
            artifact_names.add(relative)
            entries.append({'path': str(contained_path(work_root, relative)), 'sha256': artifact['sha256']})
        errors.extend(verify_files(entries))
        missing = set(phase['required_artifacts']) - artifact_names
        if missing:
            errors.append(f'required artifacts not attested: {sorted(missing)}')
        for key in phase['required_checks']:
            check = receipt.get('checks', {}).get(key, {})
            if check.get('passed') is not True or check.get('evidence') not in artifact_names:
                errors.append(f'required check lacks passing hashed evidence: {key}')
        if not isinstance(receipt.get('notes'), str) or not receipt['notes'].strip():
            errors.append('receipt needs actual execution notes')
    except (OSError, KeyError, ValueError, TypeError) as exc:
        errors.append(f'invalid receipt: {exc}')
    return errors


def next_phase(plan, plan_hash, snapshot_hash, work_root, audit_passed):
    if not audit_passed:
        return {'status': 'blocked', 'next_phase': 'P00', 'action': 'Resolve input audit errors; never auto-accept new hashes.'}
    completed = ['P00']
    dependency_hashes = {}
    for phase in plan['phases'][1:]:
        receipt_path = contained_path(work_root, f'{plan["receipt_root"]}/{phase["id"]}.json')
        if not receipt_path.exists():
            # A future receipt must not let an executor skip this missing predecessor.
            later = [p['id'] for p in plan['phases'] if p['id'] > phase['id']
                     and contained_path(work_root, f'{plan["receipt_root"]}/{p["id"]}.json').exists()]
            return {'status': 'blocked' if later else 'pending', 'next_phase': phase['id'],
                    'title': phase['title'], 'completed_integrity_checked': completed,
                    'out_of_order_receipts': later, 'implementation': phase['implementation_status'],
                    'action': f'Read {phase["task_document"]} section {phase["id"]}. Implement and verify before claiming completion.',
                    'authorization': 'Preparation alone does not authorize execution; use the executor prompt only after user activation.'}
        errors = verify_receipt(phase, receipt_path, plan, plan_hash, snapshot_hash, work_root, dependency_hashes)
        if errors:
            return {'status': 'blocked', 'next_phase': phase['id'], 'errors': errors,
                    'completed_integrity_checked': completed}
        dependency_hashes[phase['id']] = sha256(receipt_path)
        completed.append(phase['id'])
        if phase['id'] == 'P09':
            decision = read_json(contained_path(work_root, 'results/design_decision.json'))
            selected = decision.get('selected_arm')
            if selected in ('no_supported_change', 'inconclusive'):
                return {'status': selected, 'next_phase': None,
                        'action': 'Retain the evidence and report the decision; no automatic formal run.'}
            if selected not in ('A', 'B', 'C', 'D', 'CD') or decision.get('full_run_justified') is not True:
                return {'status': 'blocked', 'next_phase': 'P09', 'errors': ['unsupported or incomplete formal design decision']}
    return {'status': 'complete_evidence_recorded', 'next_phase': None,
            'meaning': 'Recorded evidence hashes/checks pass; scientific claims still require reading the actual reports.'}


def write_new_json(path, value):
    path = Path(path)
    # No parents are created and no prior output is overwritten.
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('audit', help='read-only asset/metadata/process audit')
    a.add_argument('--output', type=Path, help='optional NEW audit JSON, never overwrites')
    sub.add_parser('next', help='audit and identify next evidence-backed phase; never execute it')
    show = sub.add_parser('show', help='print one implementation card and its required outputs/checks')
    show.add_argument('phase', choices=[f'P{i:02}' for i in range(13)])
    args = parser.parse_args(argv)
    try:
        plan = read_json(PLAN)
        if args.command == 'show':
            phase = next(p for p in plan['phases'] if p['id'] == args.phase)
            doc = (ROOT / phase['task_document']).read_text(encoding='utf-8')
            match = re.search(rf'(?ms)^## {args.phase} .*?(?=^## P\d\d |\Z)', doc)
            if not match:
                raise ValueError('implementation card missing')
            print(match.group(0).strip())
            print(json.dumps(phase, indent=2, ensure_ascii=False))
            return 0
        result = audit()
        if args.command == 'audit':
            if args.output:
                write_new_json(args.output, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result['status'] == 'pass' else 2
        outcome = next_phase(plan, sha256(PLAN), sha256(ASSETS), Path(plan['proposed_work_root']), result['status'] == 'pass')
        if result['live'].get('training_processes'):
            outcome['active_trainers_require_identity_check'] = result['live']['training_processes']
            outcome['launch_warning'] = 'Do not start another trainer. Inspect markers and the exact child process first.'
        if result['errors']:
            outcome['audit_errors'] = result['errors']
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
        return 2 if outcome['status'] == 'blocked' else 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
