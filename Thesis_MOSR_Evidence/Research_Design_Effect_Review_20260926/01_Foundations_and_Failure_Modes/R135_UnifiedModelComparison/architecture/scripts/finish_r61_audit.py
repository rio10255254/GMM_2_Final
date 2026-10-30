from r135_common import *
import pandas as pd,shutil,re
from scipy.io import loadmat
def main():
    out=ROOT/'results/r61_training_audit';s=load(out/'summary.json');targets=pd.read_csv(out/'SEM_target_matches.csv');roster=pd.read_csv(out/'training_roster.csv');training=targets[(targets.split=='train')&(targets.feature=='pillar')];ids=sorted(int(v) for v in training.sem_id.unique());assert len(ids)==35
    lab=REPO/'LabSystem_MOSR';r58=lab/'Training_Data/r60_full_power/hs100mg_basler/r58_frac050_train/manifest.json';r58m=load(r58);refs=pd.read_csv(out/'SEM_reference_values.csv');means={k:float(refs[k].mean()) for k in ['pillar','via']};assert all(abs(means[k]-r58m['sem_radius_nm'][k])<1e-9 for k in means)
    manifest=load(lab/'Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16/manifest.json');mean_checks=0
    for r in manifest['pairs']:
        if r['role']=='sequence_guard':assert abs(r['sem_radius_nm']-means[r['feature']])<1e-9;assert abs(r['target_radius_nm']-(r['sem_radius_nm']+.5*(r['source_radius_nm']-r['sem_radius_nm'])))<1e-9;mean_checks+=1
    variables=['truth_cells','truth_masks','global_index'];current=loadmat(ROOT/'validation/sem_reference.mat',variable_names=variables);bridges=[]
    for name in ['R69_ACMContourSEMValidation','R70_V42ACMContourSEMValidation']:
        path=REPO/f'Experiments/{name}/results/masks/acm_primary_masks.mat';old=loadmat(path,variable_names=variables);assert all(np.array_equal(current[k],old[k]) for k in variables);bridges.append(dict(source=record(path),all_reference_arrays_exact=True))
    soup_path=load(out/'lineage.json')['unresolved_older_checkpoint'];soup=torch.load(soup_path,map_location='cpu');save(out/'reference_scope.json',dict(current_SEM_pillar_count=36,individual_SEM_pillar_ids_in_train=ids,individual_SEM_pillar_ids_only_in_final_val=[10],SEM_pillar_train_rows=len(training),sequence_guard_train_rows=int(((roster.role=='sequence_guard')&(roster.split=='train')).sum()),all_sequence_guard_rows_checked=mean_checks,whole36_reference_means=means,mean_reference=record(r58),current_SEM_matches_original_reference_arrays=bridges,SEM_source_code=record(REPO/'Experiments/R69_ACMContourSEMValidation/scripts/run_acm_extraction.m'),inherited_soup_checkpoint=record(soup_path),inherited_soup_metadata=soup.get('soup_meta'),older_ancestry_not_fully_closed=True))
    report=ROOT/'reports/R135_R61_TRAINING_AUDIT.md'
    text='''# R61 v16訓練資料與評估答案關係審查

2026-09-16。審查的是R135真正比較、先前推薦的R61 v16 best_tradeoff，SHA-256為9821d58cc9fcf323cda0cdced0a3ea9ac39fa7acd4e7e51927c6a82e873b288b。沒有修改權重、資料、原始量測結果或受保護的預期雜湊。

## 結論

**是，已確認R61訓練使用了與目前SEM評估共用的尺寸答案。** 這不是只看到「SEM」字樣的推測：實際訓練名單中有目前36顆柱體尺寸表之35個逐顆半徑，用來生成訓練目標；另有以全36顆平均SEM尺寸製作的修正目標。

不能因此說模型毫無用處，也不能推定任何人的動機。但這批SEM成績不應被當作「模型沒有見過這些尺寸答案」的獨立驗證。先前優先推薦R61時，對資料独立性的核對不足，推薦的依據需要修正；原實測分數保留，解讀加上此限制。

## 已確認的證據

1. **實際訓練路徑確實讀入這批資料。** v16訓練日誌記錄資料包r61_universal_boundary_train_motion_texture_step_guard_v16、stage36_sem_truth_anchor與stage35_sequence_guard，並明確記錄載入外部分組名單。共20,296對，訓練18,266對、驗證2,030對。日誌開頭的「fixed_split=OFF」是另一個重現模式開關，後面有實際載入external fixed split，不能只截取該標頭判斷。
2. **SEM答案相關資料確實進入訓練名單。** sem_truth_anchor共1,400對，其中1,284對在訓練、116對在驗證。訓練部分包括674筆柱體及610筆圓孔；柱體逐顆尺寸涉及35個ID，只有ID10的逐顆尺寸在此末階段的驗證組。這些是訓練名單及載入路徑證據，沒有逐樣本完整讀取帳，因此不將每一筆名單等同於逐筆讀取的直接證明。
3. **不是同名不同資料表。** R60上游CSV的72個柱／孔半徑，與目前SEM來源資料夾via_pilar.xlsx的36列兩欄一致，最大差2.28e-13nm。該表的6×6柱體編號配置與目前SEM對照一致；R135使用的truth_cells、truth_masks、global_index也逐項與R69、R70原始SEM參考陣列完全一致。R69取圖程式明確使用同一SEM_data目錄的P-01至P-09。
4. **實際輸入與答案圖有重新製作核對。** 852筆真實裁切來自2026-06-18__17-10-31.bmp，涉及71個柱／孔特徵。使用原始照片、記錄座標及純生成函數重新製作裁切和目標，852對均逐像素一致。其中780對在訓練名單，72對在驗證。
5. **目標不是完整SEM照片的逐像素複製。** 程式讀取SEM半徑，按69nm/像素換算，在原圖偵測到的位置畫圓形目標；可包含周圍鄰居。這證明使用了SEM尺寸答案，不等於已證明直接把SEM完整不規則輪廓圖當標籤，也不把程式的ID對應當作已獨立認證的物理逐顆配準。
6. **還有平均尺寸的監督。** sequence_guard共1,200對，其中1,068對在訓練名單。全數以同一SEM表的柱體平均1321.882002nm／孔平均1641.998647nm為依據，目標把來源尺寸往該均值修正一半。即使ID10的個別答案未進末階段訓練名單，也不能據此把它稱完全未接觸的未知樣品，因為全體平均值仍有使用。

## 內部分組與外部評估必須分開

末階段SEM逐顆ID的訓練／驗證交集確實為0，沒有把這個結果改寫成錯誤。但現在對外評估使用全部36顆，包含訓練名單已用的35顆。內部分組正確，不代表另外拿來評分的整批SEM與訓練獨立。資料包的anti_answer_leakage_design旗標也不能替代此來源核對。

## 沒有證明的部分

- 目前201張位移影像加正常3張SEM配對光學圖，其完整解碼像素沒有任何一張等於上述June18訓練母圖。因此本次**未證明這201張照片原封不動進入v16末階段訓練**。這個比對不能排除不同裁切、縮放、其他上游來源或繼承權重的接觸；也不能只凭日期或不同資料夾宣稱獨立。
- June18照片本身曾是另一路靜態重建／尺寸評估樣張，卻也是這852筆訓練裁切的母圖。這條同照片訓練來源是明確的，不能泛化成目前所有201張照片都有同樣情況。
- R61不是從零訓練。v16接續v14，再接續r39_best_latest_a970混合權重；其元資料指出更早的best/latest來源。兩個已追到的訓練階段都只訓練8個boundary_adapter參數張量、凍結115個。v16與直接母權重相比，除8個adapter張量及weak_psf_block.beta_scale外，其餘126項狀態完全相同。更早完整資料祖譜仍未封閉，不能認證「其他所有資料都沒有重疊」。
- 此審查證明答案來源接觸，**沒有量化這造成多少分數優勢**。不能把R61與其他模型的全部差距歸因於它。

## 對目前選擇的影響

R61的6.59nm細形狀差距等數字仍是實際量到的結果，但應標示「使用相關SEM尺寸監督的歷史模型」。舊V42的已知評估來源／尺寸重用問題仍保留，各自證據不混為一談。R61不能作為排除評估答案問題後的乾淨替代品。

若接下來要證明對未知樣本有用，需要排除相關評估照片、衍生裁切、SEM逐顆及均值答案，並檢查繼承模型／教師的資料來源；再使用獨立實物樣本驗證。只移除v16最後一段的SEM資料而沿用既有權重，不足以證明乾淨重訓。本次不自動重訓或替換模型。

## 可重算資料

- scripts/audit_r61_training.py、scripts/finish_r61_audit.py：讀取、重建與交叉核對。
- results/r61_training_audit/training_roster.csv、role_counts.csv：實際分組映射與數量。
- SEM_target_matches.csv、SEM_reference_values.csv：逐筆SEM答案數值關係。
- real_crop_and_target_replay.csv：852對輸入及目標圖重建核對。
- evaluation_full_image_identity.csv：204張完整影像的解碼像素比對。
- lineage.json、inherited_tensor_comparison.json、reference_scope.json：訓練繼承、資料與參考來源。

原R135比較報告、圖表及完成記錄不覆寫；本審查另行補充其資料來源限制。
'''
    report.write_text(text,encoding='utf-8');before=out/'index_before';before.mkdir(exist_ok=False)
    for p in [REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',ROOT/'README.md']:shutil.copy2(p,before/p.name)
    p=REPO/'PROJECT_STATE.md';t=p.read_text(encoding='utf-8-sig');notice='**R61資料審查（2026-09-16）：** 已確認目前36顆SEM尺寸表中35顆數值用於R61訓練目標，另有全體平均尺寸監督；1284筆SEM答案相關資料在末階段訓練名單，852裁切／目標逐像素重現。R61不可視為排除評估答案後的乾淨替代品；原分數不改，未證明目前201張位移照片全部直接進訓練，完整祖譜未封閉。[審查](Experiments/R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md)';t=t.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+notice,1);t=t.replace('<!-- R135_END -->',notice+'\n<!-- R135_END -->',1);t=re.sub(r'(?m)^Last updated:.*$','Last updated: 2026-09-16（R61已確認共用SEM尺寸監督；更正資料獨立性解讀）',t,count=1);p.write_text(t,encoding='utf-8')
    p=REPO/'ESTIMATOR_POLICY.json';v=load(p);x=next(x for x in v['open_side_tracks'] if x.get('candidate_id')=='r135_comparison');x.update(r61_same_SEM_reference_in_training=True,r61_individual_eval_pillar_ids_in_final_train=35,r61_training_audit='Experiments/R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md',r61_current201_direct_photo_reuse_not_established=True,model_promoted=False);atomic(p,v)
    p=REPO/'Experiments/INDEX.md';t=p.read_text(encoding='utf-8-sig');t=re.sub(r'(?m)^\| R135 .*$', '| R135 統一模型比較 | [結果](R135_UnifiedModelComparison/reports/R135_RESULTS.md)／[R61資料審查](R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md) | 7組比較完成；R61確認使用35顆評估SEM尺寸值及均值監督，不能當乾淨替代；數值結果保留 |',t);p.write_text(t,encoding='utf-8')
    p=ROOT/'README.md';t=p.read_text(encoding='utf-8');p.write_text(t+'\n\n**資料來源解讀更新：** [R61訓練資料審查](reports/R135_R61_TRAINING_AUDIT.md)確認35顆評估SEM尺寸值進入末階段訓練目標；數值成績保留，不能把R61當成未使用相關答案的替代品。\n',encoding='utf-8')
    verify();assert all(sha(r['path'])==r['sha256'] for r in s['inputs']);delivery=load(ROOT/'results/delivery_complete.json');assert sha(delivery['report']['path'])==delivery['report']['sha256'];save(out/'complete.json',dict(report=record(report),original_data_weights_and_comparison_report_unchanged=True,individual_eval_SEM_pillars_in_train=35,SEM_supervision_training_rows=1284,real_crop_pairs_reproduced=852,no_promotion=True));print('R61 audit complete:35of36SEMsize references in training; originals unchanged')
if __name__=='__main__':main()
