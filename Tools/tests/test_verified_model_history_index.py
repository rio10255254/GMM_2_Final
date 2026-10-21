"""Model identity must not be guessed from file bytes, epoch or an alias name."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_verified_model_history_index import state_equivalence_groups, epoch_name_differences


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
