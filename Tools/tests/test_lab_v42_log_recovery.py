"""Guard against silently assigning historical V42 values to wrong columns."""
import csv
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from replay_lab_v42_history import original_log_layout, read_original_log, verify_stdout

TRAINER = TOOLS.parent / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/V42_SoftLabelSNR_FullStandalone_20260709/train_v42.py'


def test_original_writer_layout_explains_both_opposite_shifts():
    old, actual, absent = original_log_layout(TRAINER)
    assert len(old) == 177 and len(actual) == 169
    assert actual.index('loss_input_lowfreq') == 12
    assert actual.index('val_ssim') == old.index('val_ssim') + 1
    assert actual.index('gmf_obj') == old.index('gmf_obj') - 8
    assert len(absent) == 9 and not set(absent) & set(actual)


def test_true_ssim_is_confirmed_by_stdout_and_original_tokens_survive(tmp_path):
    old, actual, _ = original_log_layout(TRAINER)
    values = ['0'] * len(actual)
    for key, value in {'epoch': '1', 'val_total': '0.2269242120774712', 'val_rec': '0.02780546761419872',
                       'val_edge': '0.23945557395410946', 'val_edge_profile': '0.0',
                       'val_psnr': '15.43748181649065', 'val_ssim': '0.7298154483629963'}.items():
        values[actual.index(key)] = value
    source = tmp_path / 'original.csv'
    with source.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(old)
        writer.writerow(values)
    before = source.read_bytes()
    rows, raw = read_original_log(source, old, actual)
    assert dict(zip(old, values))['val_ssim'] == '15.43748181649065'
    assert rows[0]['val_ssim'] == '0.7298154483629963'
    assert raw == [values] and source.read_bytes() == before
    assert verify_stdout(rows, '-> Epoch 1 Val Done. Total=0.226924 | Rec=0.027805 | Edge=0.239456 | EdgeProf=0.000000 | PSNR=15.44 | SSIM=0.7298') == 6
    with pytest.raises(ValueError, match='disagrees'):
        verify_stdout(rows, '-> Epoch 1 Val Done. Total=0.226924 | Rec=0.027805 | Edge=0.239456 | EdgeProf=0.000000 | PSNR=15.44 | SSIM=0.9999')


def test_a_different_incomplete_row_cannot_be_silently_repaired(tmp_path):
    old, actual, _ = original_log_layout(TRAINER)
    source = tmp_path / 'incomplete.csv'
    with source.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(old)
        writer.writerow(['1'] * 168)
    with pytest.raises(ValueError, match='exact original'):
        read_original_log(source, old, actual)
