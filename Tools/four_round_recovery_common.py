"""Stable identities for the R94/R95/R97/R98 preservation audit."""
from pathlib import Path
import hashlib
import json

ROUNDS = {
    94: 'R94_EvidenceConditionalScratch',
    95: 'R95_CounterfactualGateRepairScratch',
    97: 'R97_DirectCausalPhaseScratch',
    98: 'R98_AggressiveTextureScratch',
}
ENDPOINTS = {94: (4, 8), 95: (40, 48), 97: (44, 48), 98: (44, 48)}
CONTENT_ID = '6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def new_output(root, output):
    output = output.resolve()
    if output.is_relative_to(root.resolve()):
        raise ValueError('Use a new output directory outside the recovered research sources')
    output.mkdir(parents=True, exist_ok=False)
    return output
