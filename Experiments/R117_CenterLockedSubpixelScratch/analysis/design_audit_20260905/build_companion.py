"""Create and execute the compact notebook companion to the design audit."""
from pathlib import Path
import json
import nbformat as nbf
from nbclient import NotebookClient

here=Path(__file__).resolve().parent
cells=[
    nbf.v4.new_markdown_cell('''# R117 design audit companion

This notebook reproduces the three read-only diagnostic scripts and loads
their evidence. It does not start training, modify experiment code, or save
weights. Detailed interpretation is in `FINDINGS.md`.

The key findings are a mislabeled R109-to-R117 preview cascade, a normal/SDF
polarity mismatch, inactive geometry-consistency training, and a whole-object
normal-distance average that is insensitive to actual x/y translation.
'''),
    nbf.v4.new_markdown_cell('''## Context and assumptions

The 72-scene diagnostic balances 12 shape families and two polarities. It is
drawn from the existing development validation pool, not a new sealed holdout.
Oracle geometry tests isolate coordinate errors and are not deployment results.
The real image reference is the pre-R109 source verified by reproducing R109.
The center-nine radial profile measures edge oscillation, not circularity truth.
'''),
    nbf.v4.new_code_cell("from pathlib import Path\nimport json, subprocess, sys\nimport pandas as pd\nhere = Path(r'Experiments/R117_CenterLockedSubpixelScratch/analysis/design_audit_20260905')\n"),
    nbf.v4.new_markdown_cell('## Reproduce the diagnostics'),
    nbf.v4.new_code_cell("for script in ['diagnose.py', 'preview_source_audit.py', 'render_mechanism_audit.py']:\n    completed = subprocess.run([sys.executable, str(here / script)], capture_output=True, text=True, encoding='utf-8', errors='replace')\n    if completed.returncode:\n        raise RuntimeError(completed.stderr[-6000:] + completed.stdout[-3000:])\n    print(script, 'passed')"),
    nbf.v4.new_markdown_cell('## Check protected inputs and actual supervision'),
    nbf.v4.new_code_cell("audit = json.loads((here / 'audit_results.json').read_text())\nassert audit['protected_files_unchanged']\nprint('Training source, final checkpoint and data manifest unchanged:', audit['protected_files_unchanged'])\nprint('Detector E6/E42 identical:', audit['checkpoint_freezing']['all_detector_tensors_bit_identical_E6_E42'])\npd.DataFrame([{ 'active': g['active_group'], 'position_pair_value':g['terms']['pair_sdf']['value'], 'position_pair_gradient':g['terms']['pair_sdf']['active_group_gradient_norm']} for g in audit['gradients']['pair_terms']])"),
    nbf.v4.new_markdown_cell('## Check normal polarity and target reachability'),
    nbf.v4.new_code_cell("summaries = audit['model_data']['summary']\npd.DataFrame([{ 'polarity': name, 'wrong_normal_fraction': summaries[name]['normal_wrong_sign_fraction']['mean'], 'native_oracle_sampling_error_px': summaries[name]['true_sdf_native_normal_sampling_error_px']['mean'], 'sign_corrected_oracle_sampling_error_px': summaries[name]['true_sdf_sign_corrected_sampling_error_px']['mean'], 'unreachable_width_target_fraction': summaries[name]['target_gain_beyond_actuator_fraction']['mean']} for name in ['bright','dark']])"),
    nbf.v4.new_markdown_cell('## Reconcile the real preview inputs'),
    nbf.v4.new_code_cell("preview = json.loads((here / 'preview_source_results.json').read_text())\nassert all(r['r109_reproduced_vs_configured_max_gray'] == 0 for r in preview['images'])\npd.DataFrame(preview['images'])[['image','raw_vs_configured_mean_gray','r109_reproduced_vs_configured_max_gray','r117_direct_change_mean_gray','r117_cascade_vs_direct_mean_gray']]"),
    nbf.v4.new_markdown_cell('## Check the claimed center metric and ring mechanism'),
    nbf.v4.new_code_cell("display(pd.DataFrame(audit['analytic']['centroid_metric_blindness']))\nrender = json.loads((here / 'render_mechanism_results.json').read_text())\npd.Series({name:p['radial_reversal_gray'] for name,p in render['pillar_profiles'].items()},name='Radial reversal, gray')"),
    nbf.v4.new_markdown_cell('''## Interpretation

Training completion and finite tensors did not establish the scientific
properties intended by the design. The normal sign, actual translation
objective, gradient path and output continuity need explicit mechanistic
checks. The frozen projection intervention reduces a ring when bypassed on
one crop; it does not select a deployable alternative. A lower horizontal
gradient energy alone is not evidence of poorer detail fidelity. The broader
model comparison still needs same-input ACM and localization validation.
'''),
]
notebook=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
path=here/'audit_companion.ipynb'
nbf.write(notebook,path)
client=NotebookClient(notebook,timeout=240,kernel_name='python3',resources={'metadata':{'path':str(here)}})
client.execute()
nbf.validate(notebook)
nbf.write(notebook,path)
print(json.dumps({'status':'executed','path':str(path),'code_cells':sum(c.cell_type=='code' for c in notebook.cells)}))
