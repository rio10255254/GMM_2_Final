"""Finalize a calculation audit, visibly separating original replay from corrected readout."""
from pathlib import Path
import sys,json,hashlib,shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/definition_audit';FIG=ROOT/'poster_assets/lsc_checked';FIG.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
from lsc_fixed_state import measure_inflection_lsc_fixed
from probe_lsc_order import reset
FIELDS=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm'];METHODS=['Raw','Wiener','V42','R152']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def mdtable(df):
    lines=['| 範圍 | 方法 | 步距波動 nm | 名義步距平均差 nm | 九顆差異 nm |','|---|---|---:|---:|---:|']
    for r in df.itertuples():lines.append(f'| {r.scope} | {r.method} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} | {r.median_within_grid_sd_nm:.6f} |')
    return '\n'.join(lines)
def main():
    assert load(OUT/'state_recheck_complete.json')['passed']
    s=pd.read_csv(OUT/'state_summary.csv');fixed=s[s.phase==0].copy();main=fixed[fixed.scope=='all120'].set_index('method')
    centers=pd.read_csv(OUT/'state_centers.csv');centers=centers[centers.phase==0];pairs=pd.read_csv(OUT/'state_pairs.csv');pairs=pairs[pairs.phase==0]
    # Recompute every pair independently from the saved corrected centers.
    idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();cfg=load(ROOT/'sources/sequence_config.json');maxerr=0
    for row in pairs.itertuples():
        a=idx.loc[(row.sequence,row.method,row.start)].sort_index();b=idx.loc[(row.sequence,row.method,row.end)].sort_index();dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*cfg['sequences'][row.sequence]['object_um_per_px']*1000
        expected=[abs(np.median(dx)),abs(abs(np.median(dx))-cfg['sequences'][row.sequence]['nominal_step_um']*1000),np.std(dx,ddof=1)]
        maxerr=max(maxerr,float(np.max(abs(np.array(expected)-[row.step_nm,row.nominal_abs_error_nm,row.within_grid_sd_nm]))))
    assert maxerr<1e-7
    definitions=[]
    for m,g in pairs.groupby('method'):
        for definition,step in [('horizontal',g.step_nm.to_numpy()),('two_dimensional',np.hypot(g.step_nm.to_numpy(),g.dy_nm.to_numpy()))]:
            h=g.copy();h['new_step']=step;nom=h.sequence.map(lambda seq:cfg['sequences'][seq]['nominal_step_um']*1000)
            definitions.append(dict(method=m,definition=definition,step_sd_nm=np.mean([v.new_step.std(ddof=1) for _,v in h.groupby('sequence')]),nominal_mae_nm=(h.new_step-nom).abs().mean()))
    defs=pd.DataFrame(definitions);defs.to_csv(OUT/'corrected_xy_definition.csv',index=False)
    examples=[]
    for m in METHODS:
        a=idx.loc[('50x_x_0p5um',m,0)].sort_index();b=idx.loc[('50x_x_0p5um',m,1)].sort_index()
        for pid in a.index:examples.append(dict(method=m,pillar_id=pid,before_x_px=a.loc[pid,'lsc_center_x_px'],after_x_px=b.loc[pid,'lsc_center_x_px'],dx_nm=(b.loc[pid,'lsc_center_x_px']-a.loc[pid,'lsc_center_x_px'])*69))
    pd.DataFrame(examples).to_csv(OUT/'worked_example_nine_pillars.csv',index=False)
    # Paired CIs compare the current and old learned models using this same fixed reader.
    rng=np.random.default_rng(20260929);boot=[];seqs=list(cfg['sequences'])
    def aggregate(m,ix):
        g=[pairs[(pairs.sequence==seq)&(pairs.method==m)].sort_values('start') for seq in seqs]
        a=np.stack([x.step_nm for x in g]);b=np.stack([x.nominal_abs_error_nm for x in g]);c=np.stack([x.within_grid_sd_nm for x in g])
        aa=np.take_along_axis(a[None],ix,2);bb=np.take_along_axis(b[None],ix,2);cc=np.take_along_axis(c[None],ix,2)
        return np.c_[aa.std(2,ddof=1).mean(1),bb.mean((1,2)),np.median(cc.reshape(len(ix),120),axis=1)]
    ix=rng.integers(0,30,size=(20000,4,30));values=aggregate('V42',ix)-aggregate('R152',ix);ci=np.percentile(values,[2.5,97.5],axis=0)
    for j,f in enumerate(FIELDS):boot.append(dict(metric=f,v42_minus_r152_nm=float(main.loc['V42',f]-main.loc['R152',f]),ci95_low_nm=ci[0,j],ci95_high_nm=ci[1,j],conditional_on_original_pairs=True))
    pd.DataFrame(boot).to_csv(OUT/'v42_r152_fixed_reader_intervals.csv',index=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,3,figsize=(14,5));colors=['#7e8a94','#c28536','#8775a3','#227b94']
    for ax,f,title in zip(axes,FIELDS,['Step SD','Nominal MAE','Median within-grid SD']):
        vals=main.loc[METHODS,f].to_numpy();bars=ax.bar(METHODS,vals,color=colors);ax.set_title(title,weight='bold');ax.set_ylabel('nm');ax.set_ylim(0,max(vals)*1.23);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+max(vals)*.03,f'{v:.2f}',ha='center',weight='bold')
    fig.suptitle('Same LSC reader with contour state reset for every pillar',fontsize=18,weight='bold',y=.97);fig.text(.5,.035,'120 original pairs. All three paired V42-minus-R152 intervals include zero.',ha='center');fig.subplots_adjust(top=.79,bottom=.16,left=.05,right=.98,wspace=.3)
    for ext in ['png','svg']:fig.savefig(FIG/f'corrected_lsc_comparison.{ext}',dpi=240)
    plt.close(fig)
    # Show the actual boundary points, fitted circle, and center; test call-order invariance.
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';fig,axes=plt.subplots(2,2,figsize=(10,9));invariance=[]
    for ri,seq in enumerate(['20x_0p5um','50x_x_0p5um']):
        spec=cfg['sequences'][seq];mag=spec['magnification'];raw=backend.load_grayscale(Path(spec['raw_dir'])/'frame_0000.bmp');folder='20x' if mag=='20x' else '50x_calibrated';recon=np.load(ROOT/f'results/{folder}/reconstruction/{seq}/frame_0000.npz')['output'].astype(float);pred=backend.session_prediction(seq,0,np.array(spec['centers'],float),spec['expected_signed_dx_px']);pid,x,y=pred[pred[:,0]==29][0];half=int(np.ceil(.46*spec['pitch_px']))
        for ci,(method,image) in enumerate([('Raw',raw),('R152',recon)]):
            patch,pc,origin=backend.crop_around(image,(x,y),half);kw=dict(sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
            reset(0);a=measure_inflection_lsc_fixed(patch,pc,spec['radius_px'],**kw);reset(1);b=measure_inflection_lsc_fixed(patch,pc,spec['radius_px'],**kw)
            error=float(np.max(abs(np.array([a.lsc.cx,a.lsc.cy,a.lsc.radius])-np.array([b.lsc.cx,b.lsc.cy,b.lsc.radius]))));assert error==0;invariance.append(dict(sequence=seq,method=method,center_radius_max_difference_px=error))
            ax=axes[ri,ci];ax.imshow(patch,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.plot(a.coarse_contour_xy[:,0],a.coarse_contour_xy[:,1],color='#ffc365',lw=1,label='Coarse contour');ax.scatter(a.inflection_points_xy[:,0],a.inflection_points_xy[:,1],s=7,color='#6dd5ed',label='Measured boundary');ax.add_patch(Circle((a.lsc.cx,a.lsc.cy),a.lsc.radius,fill=False,color='#50e890',lw=1.3));ax.plot(a.lsc.cx,a.lsc.cy,'+',color='#fa695a',ms=11,mew=1.5);ax.set_title(f'{mag} {method} | pillar 29');ax.axis('off')
    fig.suptitle('Actual boundary points -> geometric LSC circle -> center',fontsize=16,weight='bold',y=.98);fig.text(.5,.025,'Orange: coarse contour. Blue: measured edge. Green: least-squares circle. Red: fitted center.',ha='center',fontsize=10);fig.subplots_adjust(top=.9,bottom=.07,hspace=.17,wspace=.08)
    for ext in ['png','svg']:fig.savefig(FIG/f'lsc_boundary_center_evidence.{ext}',dpi=230)
    plt.close(fig)
    effect=pd.read_csv(OUT/'state_center_effect.csv').groupby('method').center_difference_nm.agg(['mean','max']);q=load(OUT/'r152_u8_summary.json');sensitivity=pd.read_csv(OUT/'sampling_seed_summary.csv');recheck=load(OUT/'state_recheck_complete.json')
    perc={f:100*(main.loc['V42',f]-main.loc['R152',f])/main.loc['V42',f] for f in FIELDS}
    report=f'''# R152 位移定義、LSC與順序敏感性稽核

## 結論

確實使用幾何最小平方法圓心（LSC），位移與單位換算重算一致。新發現的缺陷在LSC之前：原投稿找粗外框的平滑運算保留跨呼叫狀態，讓相同影像的圓心受處理順序影響。完整11952次圓擬合確認此現象，固定起始狀態後已對四方法全部120配對重算。

這個缺陷必須修，但修完R152仍只有小幅超過舊V42，不是原計算誤差把突破性提升藏住。50×兩項仍落後V42，不能只看合併數值宣布全面升級。

## LSC究竟做了什麼

每顆柱子先找粗外框，沿法線取正確亮暗方向的最大梯度點，再最小化「每點到圓心的距離減半徑」的平方和，同時求圓心及半徑。這是幾何LSC，不是用粗外框的重心當圓心，也不是把神經模型輸出位置當答案。

LSC僅負責每顆圓心；九顆合成一步的規則另外定義。對柱子j：dx_j=(後一張x_j−前一張x_j)×物方比例；一步=abs(median(dx_1…dx_9))。先做九顆各自前後差，才取中位數；不是先取兩張九顆中心中位數再相減。y位移另存，本實驗主表沿用原稿水平步距。

20×一次乘0.1725 μm/px，50×一次乘0.069 μm/px，最後換成nm。由4482筆原圓心獨立重算360筆原配對一致；已知圓與已知平移的LSC純幾何測試通過。可逐顆回算的第一對例子見 `results/definition_audit/worked_example_nine_pillars.csv`。

## 順序缺陷：原因與完整驗證

skimage的粗外框平滑使用兩種交替運算，原 `reference_circle_core.py` 未在每顆之前重設；13／15次均為奇數，跑完一顆就換到另一個起點。不同方法、柱子或影格在串列中的順序因此會影響外框，再傳給後面的取邊與LSC。R152原930張驗證介面原本已有逐顆重設，本次為重現投稿而沿用了未重設的旧讀法。

完整166張、Raw／Wiener／V42／R152、兩個固定起點，共11952次圓擬合、960筆配對。按原執行順序推回各顆起點，能重現四方法全部原圓心，最大差{max(recheck['original_center_max_difference_px'].values()):.3g}像素，證實差異來源就是保留的狀態，不是模型、影像或尺度換錯。

| 方法 | 同圖不同起點的圓心平均差 nm | 最大差 nm |
|---|---:|---:|
'''+ '\n'.join(f'| {m} | {effect.loc[m,"mean"]:.6f} | {effect.loc[m,"max"]:.6f} |' for m in METHODS)+f'''

修正採與原R152驗證相同的固定起點，逐顆重設；另一個固定起點只作敏感性檢查，沒有按分數選好看的版本。新的 `lsc_fixed_state.py` 另外保留並恢復呼叫者狀態；真實Raw/R152、20×/50×的順序切換測試為精確零差。

之前只核對了原稿數字能否重現，沒有檢查處理順序不應影響同一張圖。先前的「核對通過」不足以排除此問題；本次補做並揭露此限制，原表保留為歷史重播版。

## 固定狀態後的公平比較

'''+mdtable(fixed[fixed.scope.isin(['all120','20x','50x'])])+f'''

R152相對V42，三項合併改善依序為{perc[FIELDS[0]]:.2f}%、{perc[FIELDS[1]]:.2f}%、{perc[FIELDS[2]]:.2f}%。50×的步距波動為V42 4.539425、R152 4.620430 nm；九顆差異為V42 2.551424、R152 2.862788 nm，兩項R152都較差。名義步距平均差則接近。

固定狀態下，V42減R152的20000次配對重抽樣95%區間分別為：步距波動[-0.200820, 0.694944] nm、名義步距平均差[-0.128334, 0.729229] nm、九顆差異[-0.716255, 1.312008] nm。**三項均包含零；即使按原配對條件化讀法，這批證據也不能確定R152稳定勝過V42。** 小幅較低的樣本平均值不等於已證明新模型有穩定優勢。部分相鄰配對共享影像，這些區間也不當作獨立重拍驗證。

相對舊重播版，R152由7.125267／5.542029／4.353063变成7.123347／5.489350／4.356654 nm。修正狀態幾乎沒有改变R152本身的合併表現，沒有帶來突破性變好。

## 位移改成二維長度會有突破嗎

下表使用同一修正後圓心，僅把水平步距改成水平／垂直合成長度；只作定義敏感性，不替换原稿指標。

| 方法 | 定義 | 步距波動 nm | 名義步距平均差 nm |
|---|---|---:|---:|
'''+ '\n'.join(f'| {r.method} | {r.definition} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} |' for r in defs.itertuples())+f'''

二維讀法對各方法皆有小幅影響，不能把改定義造成的變化當成模型進步。平均代替中位數的原圓心敏感性也已保存；沒有顯示只要換合成方式就能產生大幅突破。

## 為什麼新模型只小幅改善

1. R152的正式設計是保留R148v2主體，主體權重凍結，只訓練較弱的新增光學修正。完整模型紀錄明載兩者實拍數值極接近；最新編號不等於一次全面位移能力升級。
2. 九顆彼此差異下降，不代表九顆共同偏離設定步距也會同幅度下降。逐顆資料顯示R152的誤差同向關聯較高，剩餘波動有較大共同成分。這可能包含真實平台步距變動或共同影像偏差；本次沒有逐張獨立位移真值，不能判定全部是平台造成，更不能宣稱已到物理極限。
3. 本輪與另一批930張／30趟比較不同：這裡是四條件、Raw事先篩選的120配對、對名義步距；930張驗證有平台回授、另一拍摄與追蹤方式。不能直接期待這裡重現另一批短步平均差約4 nm。
4. R152在50×没有全面超過旧V42。光學來源接對不等於網路已針對50×全面最佳化；目前證據只支持本批實測結果，不能拿「萬用」假設替代驗證。

## 額外排查

- 把R152改為與舊V42相同的8位元顯示精度，再使用固定狀態讀法，三項為{q['step_sd_nm']:.6f}／{q['nominal_mae_nm']:.6f}／{q['median_within_grid_sd_nm']:.6f} nm。與原生浮點差異很小，沒有顯示精度差遮住突破性改善；這只匹配輸出精度，不是完整控制所有模型訓練因素。
- 第一張鎖定影像的36顆逐方法檢查中，64／96改為720點讓R152圓心平均改變約0.226 nm、最大0.618 nm；Raw平均約5.75 nm、最大13.02 nm。這是取點敏感性，不是真值準確度，不將720點自動當成比較贏的版本。
- 搜尋中心改±0.5像素，R152抽查最大圓心變化約0.000235 nm；沒有發現這批抽查靠種子直接鎖住答案。原定位窗口仍由名義位移預測，因此只能說LSC目標函數不含指令，不能說整條流程完全不用指令。
- 所有已算邊界的梯度方向均為正。R152兩起點合計有4個取邊點到達搜尋邊界，保留未刪，不因结果調整排除規則。

## 使用方式與範圍

原稿重播表保留在 `results/full120/`；本次修正表在 `results/definition_audit/state_summary.csv` 的phase=0，全部修正圓心與逐對資料都有保存。phase=1是另一固定起點的敏感性對照，不用它挑最佳結果。

目前可確認：LSC及位移算式本身正確；舊找外框流程有順序依賴，已提供無順序依賴的讀取入口並完整重算。修正後仍只有相對V42的小幅改善，尚不足以說最新模型有突破性位移進步。

未更動模型、光學資料、原配對、正式基準或原投稿PDF；沒有重新訓練。新圖見 `poster_assets/lsc_checked/`。
'''
    (ROOT/'reports/R152_DISPLACEMENT_AUDIT.md').write_text(report,encoding='utf-8')
    save(OUT/'audit_verification.json',dict(passed=True,corrected_pairs_checked=480,corrected_centers=5976,center_to_pair_max_difference_nm=maxerr,order_invariance_checks=invariance,known_circle_lsc_verified=load(OUT/'calculation_verification.json')['passed'],full_order_cause_verified=True,no_new_inference_or_training=True,original_results_preserved=True))
    # Flag old results without overwriting their numbers or image outputs.
    note='> **位移讀法更新：** 後續發現原找外框程序有處理順序依賴。本頁數字保留為原稿重播版；目前請一併閱讀[LSC與位移稽核](R152_DISPLACEMENT_AUDIT.md)及其中的固定狀態重算結果。\n\n'
    history=ROOT/'reports/history_before_lsc_audit';history.mkdir(exist_ok=True)
    for name in ['R152_RESULTS.md','R152_AUDIT.md']:
        p=ROOT/'reports'/name
        if not (history/name).exists():shutil.copyfile(p,history/name)
        text=p.read_text(encoding='utf-8')
        if not text.startswith('> **位移讀法更新'):p.write_text(note+text,encoding='utf-8')
    p=ROOT/'README.md';text=p.read_text(encoding='utf-8');banner='> **最新檢查：** 原稿找外框流程有順序依賴，已固定狀態並重算四方法全部120配對。[查看LSC與位移稽核](reports/R152_DISPLACEMENT_AUDIT.md)。舊表保留作重播紀錄。\n\n'
    if not text.startswith('> **最新檢查'):p.write_text(banner+text,encoding='utf-8')
    for name in ['START_HERE.md','POSTER_TEXT.md']:
        p=ROOT/'poster_assets/full120'/name;text=p.read_text(encoding='utf-8');prefix='> **讀值待依修正版引用：** 原稿讀法發現順序依賴，此處原圖保留；更新數字與新舊模型比較請見[位移稽核](../../reports/R152_DISPLACEMENT_AUDIT.md)。\n\n'
        if not text.startswith('> **讀值待依修正版引用'):p.write_text(prefix+text,encoding='utf-8')
    print(main.to_string());print('corrected verification',maxerr)
if __name__=='__main__':main()
