"""Finalize the completed R108B negative mechanism result."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SUMMARY=ROOT/'results/summary.json'


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main()->int:
    summary=json.loads(SUMMARY.read_text(encoding='utf-8'))
    translation=json.loads((ROOT/'results/translation_response.json').read_text(encoding='utf-8'))
    if summary.get('status')!='complete':raise RuntimeError('Microprobe summary is incomplete')
    if summary['data_manifest']['counts']!={'train':384,'validation':96,'holdout':96}:raise RuntimeError('Unexpected data counts')
    for name in ('direct_parallel','joint_unsupervised_gate','staged_selector'):
        path=ROOT/'weights'/f'{name}.pth'
        if not path.exists():raise FileNotFoundError(path)
    held=summary['arms'];tile=summary['tile'];real=summary['real']
    decision={
        'status':'complete',
        'experiment':'R108B_StagedParallelOpticalExpertsMicroprobe',
        'verdict':'FIXED_BASIS_FULL_IMAGE_DESIGN_REJECTED_SPECIALIST_DIRECT_SUPERVISION_REQUIRED',
        'formal_training_authorized':False,
        'old_checkpoint_or_teacher_used':False,
        'real_training_pixels':False,
        'execution_history':{
            'proposal_training':'Both 900-step proposal arms completed once from independent random initialization.',
            'selector_first_attempt':'Stopped before selector step 1 because an inference-only target tensor could not be saved for backward.',
            'repair':'Changed only the oracle-target tensor context; loaded the already completed proposal checkpoints and trained the selector once.',
            'halo_revalidation':'Loaded all completed checkpoints without training and repeated evaluation with the correct 96-pixel halo.',
        },
        'positive_evidence':{
            'holdout_raw_mae_gray':held['direct_parallel']['holdout']['raw_mae_gray'],
            'holdout_best_model_mae_gray':min(value['holdout']['model_mae_gray'] for value in held.values()),
            'holdout_improved_fraction':held['direct_parallel']['holdout']['mae_improved_fraction'],
            'holdout_median_iou':held['direct_parallel']['holdout']['median_iou'],
            'holdout_centroid_error_px':held['direct_parallel']['holdout']['median_centroid_error_px'],
            'internal_seam_mean_gray':tile['direct_parallel']['seam_mean_abs_gray'],
            'internal_seam_max_gray':tile['direct_parallel']['seam_max_abs_gray'],
            'subpixel_translation_mean_gray':translation['results']['direct_parallel']['mean_abs_gray'],
            'subpixel_translation_p99_gray':translation['results']['direct_parallel']['p99_abs_gray'],
        },
        'decisive_failures':{
            'edge_expert_collapsed_gray':held['direct_parallel']['holdout']['branch_abs_gray']['edge'],
            'denoise_expert_dominated_gray':held['direct_parallel']['holdout']['branch_abs_gray']['denoise'],
            'texture_expert_gray':held['direct_parallel']['holdout']['branch_abs_gray']['texture'],
            'real_fine_detail_ratio':real['direct_parallel']['fine_detail_ratio'],
            'real_strong_edge_gain':real['direct_parallel']['edge_gain'],
            'identity_change_gray':held['direct_parallel']['holdout']['identity_change_gray'],
            'added_topology_failures':held['direct_parallel']['holdout']['added_topology_failures'],
            'joint_gate_mean':held['joint_unsupervised_gate']['holdout']['alpha_mean'],
            'joint_gate_identity_mean':held['joint_unsupervised_gate']['holdout']['alpha_identity_mean'],
            'staged_selector_mean':held['staged_outcome_selector']['holdout']['alpha_mean'],
            'staged_selector_identity_mean':held['staged_outcome_selector']['holdout']['alpha_identity_mean'],
        },
        'root_cause':[
            'Removing a common gate does not remove the identity shortcut when every expert amplitude remains free under only final-image supervision.',
            'The edge expert drove its own amplitude near zero, while denoising supplied nearly all of the synthetic loss improvement.',
            'The proposal therefore looked broadly useful to the staged selector, causing adoption to saturate near one instead of separating identity and restoration cases.',
            'Synthetic MAE improvement was not aligned with real microscopy detail preservation; real fine detail fell to roughly 37 percent of Raw.',
        ],
        'revised_direction':{
            'name':'R108C_IndependentlySupervisedOpticalSpecialists',
            'requirements':[
                'Train the edge specialist only on explicit center, width, endpoint-level and local-profile targets; do not let whole-image loss set its amplitude.',
                'Train the texture specialist only on target-supported phase and band-gain targets, with paired observations distinguishing structure from noise.',
                'Train denoising only on paired independent-noise views and prevent it from updating edge/texture specialists.',
                'Train low-frequency radiometry on zero-mean illumination fields with a geometry-neutrality target.',
                'Freeze and test every specialist on its own unseen roles before any composition or adoption network is introduced.',
                'Only after specialists pass, train per-specialist adoption factors from direct counterfactual improvement targets; never one shared global gate.',
                'Keep the local fully convolutional path and at least a 96-pixel halo; handle the outer image border separately from internal seams.',
            ],
            'next_probe':'Four independent specialist micro-overfits and held-out tests; no combined model until every specialist is causally active.',
        },
        'not_authorized':['full R108 training','ONNX export','enterprise delivery','reuse of R108B weights in a formal model','replacement of any current model'],
    }
    (ROOT/'results/final_decision.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    f=decision['decisive_failures'];p=decision['positive_evidence']
    report='\n'.join([
        '# R108B 二維小型探針結果','',
        '## 結論','',
        '目前的固定基底平行專家設計被否決，不進入完整訓練。分塊核心已證明安全，但模型再次用去噷取代真正的邊界與紋理重建。','',
        '## 正向結果','',
        f"- 未見形狀與嚴重退化的整體誤差由 {p['holdout_raw_mae_gray']:.3f} 降到 {p['holdout_best_model_mae_gray']:.3f} 灰階。",
        f"- {100*p['holdout_improved_fraction']:.1f}% 影像的平均誤差下降；輪廓中位 IoU 為 {p['holdout_median_iou']:.4f}。",
        f"- 96 px halo 下，內部接縫平均／最大差異為 {p['internal_seam_mean_gray']:.8f}／{p['internal_seam_max_gray']:.8f} 灰階。",'',
        f"- 已知次像素平移的一致性平均／P99 差異為 {p['subpixel_translation_mean_gray']:.4f}／{p['subpixel_translation_p99_gray']:.4f} 灰階。",'',
        '## 決定性失敗','',
        f"- 邊界專家實際作用只剩 {f['edge_expert_collapsed_gray']:.4f} 灰階，去噪專家則為 {f['denoise_expert_dominated_gray']:.3f} 灰階。",
        f"- 真實影像細節只剩 Raw 的 {100*f['real_fine_detail_ratio']:.1f}%，強邊界也降到 {100*f['real_strong_edge_gain']:.1f}%。",
        f"- 未見資料新增 {f['added_topology_failures']} 個拓撲失敗；清楚影像平均被改動 {f['identity_change_gray']:.3f} 灰階。",
        f"- 共同開關在 identity 上仍為 {f['joint_gate_identity_mean']:.3f}，分階段選擇器則為 {f['staged_selector_identity_mean']:.3f}，兩者都沒有學會關閉不必要修正。",'',
        '## 下一個設計','',
        'R108C 不先做組合模型。邊界、紋理、去噪與亮度四個專家必須各自用自己的明確物理答案獨立訓練、獨立通過未見資料，再凍結專家訓練各自的採用比例。任何專家若再次靠把振幅降到零通過，就立即否決該專家，不讓它躲進整體平均。',''
    ])
    (ROOT/'reports/R108B_RESULTS_ZH.md').write_text(report,encoding='utf-8')
    state={'status':'complete','experiment':'R108B_StagedParallelOpticalExpertsMicroprobe','formal_model_trained':False,'verdict':decision['verdict'],'final_decision':'results/final_decision.json','next_probe':decision['revised_direction']['next_probe']}
    (ROOT/'EXPERIMENT_STATE.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    files=sorted(path for path in ROOT.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name!='FILE_MANIFEST_SHA256.csv');rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in files]
    with (ROOT/'FILE_MANIFEST_SHA256.csv').open('w',newline='',encoding='utf-8-sig') as handle:writer=csv.DictWriter(handle,fieldnames=['path','bytes','sha256']);writer.writeheader();writer.writerows(rows)
    print(json.dumps(state,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
