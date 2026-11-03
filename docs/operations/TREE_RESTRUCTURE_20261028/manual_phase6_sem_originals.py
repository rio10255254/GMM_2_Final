"""Point the scripts that read the original SEM images at Shared_Sources/SEM_Originals.

H:/From_2TB_D_disk/13_thesis/SEM_data holds 25 files; every one restores from the cloud to the same
relative path under Shared_Sources/SEM_Originals with the same sha256 (checked 2026-11-03).
"""
from pathlib import Path

H_BS = r'H:\From_2TB_D_disk\13_thesis\SEM_data'
H_FS = 'H:/From_2TB_D_disk/13_thesis/SEM_data'
E = {
    'Experiments/R103_RecoverableDetailScratch/analysis/run_causal_alpha_probe.py':
        [(f'SEM_DIR = Path(r"{H_BS}")', "SEM_DIR = PROJECT_ROOT / 'Shared_Sources/SEM_Originals'")],
    'Experiments/R113_CausalStructureDissection/scripts/run_sem_intervention_acm.py':
        [(f'SEM = Path(r"{H_BS}")', "SEM = PROJECT_ROOT / 'Shared_Sources/SEM_Originals'")],
    'Experiments/R127_MeasurementPreservationRepair/scripts/sem_native_audit.py':
        [(f"path=Path(r'{H_BS}')/f'P-{{file:02d}}.tiff'", "path=REPO/'Shared_Sources/SEM_Originals'/f'P-{file:02d}.tiff'")],
    'Experiments/R127_MeasurementPreservationRepair/scripts/sem_native_audit_v2.py':
        [(f"path=Path(r'{H_BS}')/f'P-{{file:02d}}.tiff'", "path=REPO/'Shared_Sources/SEM_Originals'/f'P-{file:02d}.tiff'")],
    'Experiments/R136_PIRepeatability/scripts/sem_reference_followup.py':
        [(f"sem=Path('{H_FS}')", "sem=PROJECT_ROOT / 'Shared_Sources/SEM_Originals'")],
    'PSF_Fitting/output/20260924_center9_psf/audit_sem_mapping.py':
        [(f'archive = Path(r"{H_BS}")', "archive = PROJECT_ROOT / 'Shared_Sources/SEM_Originals'")],
    'Experiments/R121_BoundaryAnchorFactorial/scripts/audit_reference.m':
        [(f"imread(sprintf('{H_FS}/P-%02d.tiff',p))", "imread(fullfile(PROJECT_ROOT, 'Shared_Sources/SEM_Originals', sprintf('P-%02d.tiff',p)))")],
    'Experiments/R121_BoundaryAnchorFactorial/scripts/prepare_pitch_reference.m':
        [(f"imread(sprintf('{H_FS}/P-%02d.tiff',p))", "imread(fullfile(PROJECT_ROOT, 'Shared_Sources/SEM_Originals', sprintf('P-%02d.tiff',p)))")],
    'Experiments/R69_ACMContourSEMValidation/scripts/run_acm_extraction.m':
        [(f"sem_dir = '{H_BS}';", "sem_dir = fullfile(fileparts(fileparts(fileparts(script_dir))), 'Shared_Sources', 'SEM_Originals');")],
    'Experiments/R69_ACMContourSEMValidation/scripts/run_acm_qa.m':
        [(f"sem_dir = '{H_BS}';", "sem_dir = fullfile(fileparts(fileparts(fileparts(script_dir))), 'Shared_Sources', 'SEM_Originals');")],
}
for f, reps in E.items():
    p = Path(f); t = p.read_bytes().decode('utf-8')
    for old, new in reps:
        assert t.count(old) == 1, (f, old, t.count(old)); t = t.replace(old, new)
    p.write_bytes(t.encode('utf-8'))
    print('ok', f)
