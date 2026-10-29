"""Phase 1 hand fix after apply: the center9 manifest writer records a project-relative path
(its test reads the record back through the project root; the tool rewrites that read)."""
from pathlib import Path

R = Path(__file__).resolve().parents[3]       # the project root
for path, old, new in [
    ('Thesis_MOSR_Evidence/Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/01_global_bads_fit/source_data/'
     'center9_pillar_fit_20x_50x/spectra/generate_absolute_spectra.py',
     '"wiener_source": str(wiener_path),', '"wiener_source": wiener_path.relative_to(PROJECT_ROOT).as_posix(),')]:
    p = R / path
    s = p.read_bytes().decode('utf-8')
    assert s.count(old) == 1 and 'PROJECT_ROOT = ' in s, path
    p.write_bytes(s.replace(old, new).encode('utf-8'))
print('reader fixes applied')
