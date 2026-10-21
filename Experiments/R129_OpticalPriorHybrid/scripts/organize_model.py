"""Separate existing arithmetic into named responsibilities without changing weights."""
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *

def main():
    source=ROOT/'model/hybrid_v2.py'
    tree=ast.parse(source.read_text(encoding='utf-8-sig'))
    definitions={n.name:n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    folder=ROOT/'model/organized';folder.mkdir(exist_ok=False)
    def write(name,body):
        with (folder/name).open('x',encoding='utf-8') as f:f.write(body+'\n')
    def extract(names):return '\n\n'.join(ast.unparse(definitions[n]) for n in names)
    write('__init__.py','from .hybrid import Hybrid\n')
    write('operators.py','"""Shared deterministic padding and upsampling; arithmetic unchanged."""\nimport torch\nfrom torch.nn import functional as F\n\n'+extract(['reflect_pad','replicate_one','Bilinear2x']))
    write('optics.py','"""Measured optical conditioning, evaluated once per input."""\nimport math\nimport torch\nfrom torch import nn\nfrom torch.nn import functional as F\nfrom .operators import reflect_pad\n\n'+extract(['MeasuredOptics']))
    hybrid=definitions['Hybrid'];methods={n.name:n for n in hybrid.body if isinstance(n,ast.FunctionDef)}
    refine=ast.unparse(methods['backbone'])
    refine=refine.replace('def backbone(self, raw):','def refine(raw, prior, step_logits, step_observer=None):').replace('self.step_logits','step_logits').replace('self.prior','prior')
    # Observer receives detached copies; it cannot mutate computation or output.
    needle='        state = (state + 0.25 * torch.sigmoid(step_logits[i]) * prior(features)).clamp(0, 1)'
    assert needle in refine
    refine=refine.replace(needle,needle+'\n        if step_observer is not None:\n            step_observer(i + 1, state.detach().clone())')
    write('reconstruction.py','"""One shared reconstruction network, reused four times."""\nimport torch\nfrom torch import nn\nfrom torch.nn import functional as F\nfrom torch.utils.checkpoint import checkpoint\nfrom .operators import reflect_pad, replicate_one, Bilinear2x\n\n'+extract(['Block','SharedDecoder'])+'\n\n'+refine)
    anchor=ast.unparse(methods['anchor']).replace('def anchor(self, raw, neural):','def anchored_output(raw, neural, kernel):').replace('k = self.anchor_kernel','k = kernel')
    write('output_policy.py','"""Original-image reference, bounded quality scaling, and brightness correction."""\nimport torch\nfrom torch.nn import functional as F\n\n'+anchor)
    # Keep registered names and constructor initialization order exactly compatible.
    body=ast.unparse(hybrid)
    old=ast.unparse(methods['backbone'])
    new='def backbone(self, raw, step_observer=None):\n    return refine(raw, self.prior, self.step_logits, step_observer)'
    body=body.replace('\n'.join('    '+line for line in old.splitlines()),'\n'.join('    '+line for line in new.splitlines()))
    old=ast.unparse(methods['anchor']);new='def anchor(self, raw, neural):\n    return anchored_output(raw, neural, self.anchor_kernel)'
    body=body.replace('\n'.join('    '+line for line in old.splitlines()),'\n'.join('    '+line for line in new.splitlines()))
    body=body.replace('def forward_details(self, raw, trace=False):','def forward_details(self, raw, trace=False, step_observer=None):').replace('self.backbone(conditioned)','self.backbone(conditioned, step_observer)')
    write('hybrid.py','"""R129 composition: optics -> four shared updates -> original-image output."""\nfrom dataclasses import dataclass\nimport torch\nfrom torch import nn\nfrom .optics import MeasuredOptics\nfrom .reconstruction import SharedDecoder, refine\nfrom .output_policy import anchored_output\n\n'+extract(['Details'])+'\n\n'+body)
    # Copy the existing boundary policy into the organized package unchanged.
    evaluation=ast.parse((ROOT/'scripts/evaluate_real.py').read_text(encoding='utf-8-sig'))
    guard=next(n for n in evaluation.body if isinstance(n,ast.FunctionDef) and n.name=='guard')
    write('inference_policy.py','"""Native input boundary retention; same policy as the saved pilot."""\nimport torch\n\n'+ast.unparse(guard))
    oldfiles=[source,ROOT/'scripts/evaluate_real.py',ROOT/'scripts/infer_image.py',ROOT/'config/plan.json',ROOT/'config/implementation_v2.json',ROOT/'results/verification.json']
    oldfiles+=list((ROOT/'runs').glob('*/initial.pth'))+list((ROOT/'runs').glob('*/step24.pth'))
    save(ROOT/'config/organization_plan.json',dict(created_utc=now(),purpose='Architecture map and behavior-preserving organization; no new modules or training',original_files=[record(p) for p in oldfiles],organized_files=[record(p) for p in folder.glob('*.py')],checks=['All eight states load with exactly identical tensors','FP32 forward and all parameter gradients exact on representative inputs','D all three full SEM fields and eight locked real motion ROIs float/PNG exact','Each of four update states traceable without changing outputs','Existing source hashes unchanged'],acceptance='exact equality; no tolerance relaxation',source=record(__file__)))
    print('Created seven organized modules; original model remains untouched')

if __name__=='__main__':main()
