"""Negative tests use disposable fixtures, never models or real training data."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('handoff_checker', ROOT / 'scripts/next_design.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
PLAN = helper.read_json(ROOT / 'reports/next_design_plan.json')
PH = helper.sha256(ROOT / 'reports/next_design_plan.json')
AH = helper.sha256(ROOT / 'reports/next_design_assets.json')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def make_receipt(work, phase_id, deps=None, decision='B'):
    phase = next(p for p in PLAN['phases'] if p['id'] == phase_id)
    artifacts = []
    for relative in phase['required_artifacts']:
        path = work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == 'results/design_decision.json':
            write_json(path, {'selected_arm': decision, 'full_run_justified': decision in ('A', 'B', 'C', 'D', 'CD')})
        elif not path.exists():
            path.write_text(f'Fixture only: {phase_id} {relative}', encoding='utf-8')
        artifacts.append({'path': relative, 'sha256': helper.sha256(path)})
    receipt = {'schema_version': 1, 'plan_id': PLAN['plan_id'], 'plan_sha256': PH,
               'input_snapshot_sha256': AH, 'phase': phase_id, 'status': 'complete',
               'completed_at_utc': datetime.now(timezone.utc).isoformat(),
               'depends_on_receipts': deps or {},
               'checks': {key: {'passed': True, 'evidence': artifacts[0]['path']}
                          for key in phase['required_checks']},
               'artifacts': artifacts, 'notes': 'Disposable receipt checker fixture, not scientific evidence.'}
    path = work / PLAN['receipt_root'] / f'{phase_id}.json'
    write_json(path, receipt)
    return phase, path, receipt


def test_live_plan_graph_and_documents():
    assert helper.validate_plan(PLAN) == []
    for name in PLAN['documents']:
        assert (ROOT / name).is_file()


def test_missing_or_changed_protected_file(tmp_path):
    path = tmp_path / 'input.txt'
    path.write_text('original', encoding='utf-8')
    entries = [{'path': str(path), 'sha256': helper.sha256(path)}]
    assert helper.verify_files(entries) == []
    path.write_text('mutated', encoding='utf-8')
    assert 'changed protected' in helper.verify_files(entries)[0]
    path.unlink()
    assert 'missing protected' in helper.verify_files(entries)[0]


@pytest.mark.parametrize('relative', ['../escape.txt', 'D:/escape.txt', '', '..'])
def test_unsafe_artifact_paths(tmp_path, relative):
    with pytest.raises(ValueError):
        helper.contained_path(tmp_path, relative)


def test_no_false_completion_from_file_existence(tmp_path):
    (tmp_path / 'MANIFEST.md').write_text('exists, not verified', encoding='utf-8')
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    assert result['status'] == 'pending' and result['next_phase'] == 'P01'


def test_bad_audit_stops_at_p00(tmp_path):
    result = helper.next_phase(PLAN, PH, AH, tmp_path, False)
    assert result['status'] == 'blocked' and result['next_phase'] == 'P00'


def test_verified_receipt_advances_one_phase(tmp_path):
    phase, path, receipt = make_receipt(tmp_path, 'P01')
    assert helper.verify_receipt(phase, path, PLAN, PH, AH, tmp_path, {}) == []
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    assert result['next_phase'] == 'P02'


@pytest.mark.parametrize('mutation', ['missing_check', 'false_check', 'unhashed_evidence', 'stale_plan', 'stale_snapshot', 'future_time', 'missing_artifact', 'changed_artifact'])
def test_invalid_receipt_never_advances(tmp_path, mutation):
    phase, path, receipt = make_receipt(tmp_path, 'P01')
    check = phase['required_checks'][0]
    if mutation == 'missing_check':
        receipt['checks'].pop(check)
    elif mutation == 'false_check':
        receipt['checks'][check]['passed'] = False
    elif mutation == 'unhashed_evidence':
        receipt['checks'][check]['evidence'] = 'unverified.json'
    elif mutation == 'stale_plan':
        receipt['plan_sha256'] = '0' * 64
    elif mutation == 'stale_snapshot':
        receipt['input_snapshot_sha256'] = '0' * 64
    elif mutation == 'future_time':
        receipt['completed_at_utc'] = '2999-01-01T00:00:00+00:00'
    elif mutation == 'missing_artifact':
        (tmp_path / receipt['artifacts'][0]['path']).unlink()
    elif mutation == 'changed_artifact':
        (tmp_path / receipt['artifacts'][0]['path']).write_text('later change', encoding='utf-8')
    write_json(path, receipt)
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    assert result['status'] == 'blocked' and result['next_phase'] == 'P01'


def test_future_receipt_cannot_skip_predecessor(tmp_path):
    make_receipt(tmp_path, 'P02', {'P01': '0' * 64})
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    assert result['status'] == 'blocked' and result['next_phase'] == 'P01'
    assert result['out_of_order_receipts'] == ['P02']


def test_changed_dependency_receipt_invalidates_descendant(tmp_path):
    _, p1, r1 = make_receipt(tmp_path, 'P01')
    make_receipt(tmp_path, 'P02', {'P01': helper.sha256(p1)})
    r1['notes'] += ' Updated after downstream work.'
    write_json(p1, r1)
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    assert result['status'] == 'blocked' and result['next_phase'] == 'P02'


@pytest.mark.parametrize('decision', ['no_supported_change', 'inconclusive', 'B', 'invented_winner'])
def test_scientific_decision_controls_formal_phase(tmp_path, decision):
    hashes = {}
    for phase in PLAN['phases'][1:10]:
        deps = {d: hashes[d] for d in phase['depends_on'] if d != 'P00'}
        _, path, _ = make_receipt(tmp_path, phase['id'], deps, decision)
        hashes[phase['id']] = helper.sha256(path)
    result = helper.next_phase(PLAN, PH, AH, tmp_path, True)
    if decision in ('no_supported_change', 'inconclusive'):
        assert result['status'] == decision and result['next_phase'] is None
    elif decision == 'B':
        assert result['status'] == 'pending' and result['next_phase'] == 'P10'
    else:
        assert result['status'] == 'blocked' and result['next_phase'] == 'P09'


def test_new_audit_output_cannot_overwrite(tmp_path):
    path = tmp_path / 'audit.json'
    helper.write_new_json(path, {'status': 'fixture'})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        helper.write_new_json(path, {'status': 'overwrite'})
    assert path.read_bytes() == original


@pytest.mark.parametrize('mutation', ['none', 'duplicate', 'wrong_split', 'wrong_manifest'])
def test_frozen_scene_selection_is_checked(mutation):
    selection = helper.read_json(ROOT / 'reports/next_design_selected_ids.json')
    manifest_path = ROOT / 'data/package/manifest.json'
    records = helper.read_json(manifest_path)['records']
    if mutation == 'duplicate':
        selection['development_bank_scene_ids'][0] = selection['development_bank_scene_ids'][1]
    elif mutation == 'wrong_split':
        selection['development_bank_scene_ids'][0] = selection['probe_scene_ids'][0]
    elif mutation == 'wrong_manifest':
        selection['base_manifest_sha256'] = '0' * 64
    errors = helper.verify_selection(selection, records, helper.sha256(manifest_path))
    assert bool(errors) == (mutation != 'none')


def test_actual_helper_show_does_not_run_model(capsys):
    assert helper.main(['show', 'P02']) == 0
    assert 'known_motion_calibrated' in capsys.readouterr().out
    assert not hasattr(helper, 'torch')
