"""Model identity must not be guessed from file bytes, epoch or an alias name."""
from pathlib import Path
import gzip
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_verified_model_history_index import state_equivalence_groups, epoch_name_differences, build


def state(sha):
    return {'sha256': sha, 'tensors': 139, 'elements_including_buffers': 4300000}


def test_different_wrappers_can_hold_the_same_model_without_proving_resume_identity():
    first = {'sha256': '1' * 64, 'has_optimizer_state': False,
             'state_dict_fingerprints': {'state_dict': state('a' * 64)}}
    second = {'sha256': '2' * 64, 'has_optimizer_state': True,
              'state_dict_fingerprints': {'ema_state_dict': state('a' * 64)}}
    groups = state_equivalence_groups([first, second])
    assert len(groups) == 1 and groups[0]['different_serialized_files'] == 2
    assert {row['state_slot'] for row in groups[0]['states']} == {'state_dict', 'ema_state_dict'}
    assert first['has_optimizer_state'] is False and second['has_optimizer_state'] is True


def test_same_epoch_does_not_merge_different_raw_and_smoothed_models():
    records = [{'sha256': '1' * 64, 'recorded_epoch': 10,
                'state_dict_fingerprints': {'state_dict': state('a' * 64), 'ema_state_dict': state('b' * 64)}},
               {'sha256': '2' * 64, 'recorded_epoch': 10,
                'state_dict_fingerprints': {'state_dict': state('b' * 64)}}]
    groups = state_equivalence_groups(records)
    assert len(groups) == 1 and groups[0]['tensor_content_sha256'] == 'b' * 64
    assert len(groups[0]['states']) == 2


def test_epoch_discrepancy_is_reported_without_relabeling_best_or_latest():
    record = {'sha256': '1' * 64, 'recorded_epoch': 9,
              'original_locations': [{'logical_path': 'run/epoch_010.pth.tar'},
                                     {'logical_path': 'run/best_tradeoff.pth.tar'},
                                     {'logical_path': 'run/latest.pth.tar'}]}
    findings = epoch_name_differences([record])
    assert len(findings) == 1 and findings[0]['filename_epoch'] == 10
    assert findings[0]['checkpoint_recorded_epoch'] == 9
    assert findings[0]['source_modified_or_epoch_reinterpreted'] is False
    assert record['recorded_epoch'] == 9


def test_all_captured_positions_survive_normalized_alias_deduplication(tmp_path):
    plan_root = tmp_path / 'model_batches'
    batch = plan_root / 'B001'
    (batch / 'bundle').mkdir(parents=True)
    original = {'sha256': 'a' * 64, 'bytes': 12}
    part = {'name': 'models.zip', 'sha256': 'b' * 64, 'bytes': 50}
    manifest = {'state': 'complete', 'files': [{'path': '__archive_objects__/a', **original}], 'assets': [part]}
    with gzip.open(batch / 'bundle/RESEARCH_ASSETS.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(manifest, stream)
    proof = {'status': 'PASS_FILE_IDENTITY_AND_RESTORATION', 'assets': [part], 'checks': [
        {**original, 'load_status': 'LOADABLE', 'exact_file_bytes_restored': True, 'all_tensors_finite': True}]}
    (batch / 'BATCH_GITHUB_RESTORE_VERIFIED.json').write_text(json.dumps(proof), encoding='utf-8')
    location = {**original, 'logical_path': 'run/model.pt', 'source': 'D:/research/run/model.pt',
                'restore_path': 'run/model.pt', 'origin': 'D_worktree', 'scope': 'run'}
    earlier = {**location, 'sha256': 'c' * 64, 'logical_path': 'earlier/model.pt'}
    for path, rows in [(plan_root / 'ALL_MODEL_LOCATIONS.jsonl.gz', [location, earlier]),
                       (tmp_path / 'HASHED_MODELS_FILES.jsonl.gz', [location, earlier,
                        {**location, 'source': 'H:/archive/run/model.pt', 'origin': 'H_snapshot'}])]:
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row) + '\n')
    plan = {'tag': 'models', 'source_files': 3, 'normalized_restore_locations': 2, 'new_unique_objects': 1,
            'batches': [{'batch': 'B001', 'folder': str(batch)}]}
    (plan_root / 'PLAN.json').write_text(json.dumps(plan), encoding='utf-8')
    result = build(plan_root / 'PLAN.json', tmp_path / 'index')
    assert result['captured_all_model_positions'] == 3
    assert result['normalized_model_plan_locations'] == 2
    assert result['new_object_original_positions'] == 2
    with gzip.open(tmp_path / 'index/MODEL_HISTORY_CONTENT_INDEX.json.gz', 'rt', encoding='utf-8') as stream:
        index = json.load(stream)
    assert {row['origin'] for row in index['objects'][0]['original_locations']} == {'D_worktree', 'H_snapshot'}
