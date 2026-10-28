"""Report real reconstruction benefit without degrading the raw comparator."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/localization_improvement';FIG=ROOT/'poster_assets/localization_improvement';FIG.mkdir(parents=True,exist_ok=True)
FIELDS=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def table(df):
    lines=['| 範圍 | 方法 | 步距波動 nm | 名義步距平均差 nm | 九顆差異 nm |','|---|---|---:|---:|---:|']
    for r in df.itertuples():lines.append(f'| {r.scope} | {r.method} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} | {r.median_within_grid_sd_nm:.6f} |')
    return '\n'.join(lines)
def main():
    done=load(OUT/'real_complete.json');assert done['passed'] and done['excluded_pairs']==0
    assert load(OUT/'real_content_validation_fresh.json')['overall_passed']
    s=pd.read_csv(OUT/'improved_summary.csv');comparison=pd.read_csv(OUT/'improvement_comparison.csv');pairs=pd.read_csv(OUT/'improved_pairs.csv');centers=pd.read_csv(OUT/'improved_centers.csv');cfg=load(ROOT/'sources/sequence_config.json');locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();maxerr=0
    for (seq,m),g in pairs.groupby(['sequence','method']):
        a=g[['start','end']].to_numpy();b=locked[locked.sequence==seq][['start_frame_index','end_frame_index']].to_numpy();assert np.array_equal(a,b) and len(g)==30
    for row in pairs.itertuples():
        a=idx.loc[(row.sequence,row.method,row.start)].sort_index();b=idx.loc[(row.sequence,row.method,row.end)].sort_index();assert len(a)==len(b)==9 and a.index.equals(b.index)
        dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*cfg['sequences'][row.sequence]['object_um_per_px']*1000
        exp=np.array([abs(np.median(dx)),abs(abs(np.median(dx))-row.nominal_nm),np.std(dx,ddof=1)])
        maxerr=max(maxerr,float(np.max(abs(exp-[row.step_nm,row.nominal_abs_error_nm,row.within_grid_sd_nm]))))
    assert maxerr<1e-7
    for row in s.itertuples():
        g=pairs[pairs.method==row.method]
        if row.scope in ['20x','50x']:g=g[g.magnification==row.scope]
        elif row.scope!='all120':g=g[g.sequence==row.scope]
        expected=[np.mean([v.step_nm.std(ddof=1) for _,v in g.groupby('sequence')]),g.nominal_abs_error_nm.mean(),g.within_grid_sd_nm.median()]
        assert np.max(abs(np.array(expected)-[row.step_sd_nm,row.nominal_mae_nm,row.median_within_grid_sd_nm]))<1e-9
    mainrows=s[s.scope=='all120'].set_index('method');old=comparison[comparison.scope=='all120'].set_index('method');relative={f:100*(mainrows.loc['Raw',f]-mainrows.loc['R152',f])/mainrows.loc['Raw',f] for f in FIELDS}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,3,figsize=(13.8,5));methods=['Raw','Wiener','R152'];colors=['#7c8791','#cf8c36','#247d91']
    for ax,field,title in zip(axes,FIELDS,['Step SD','Nominal MAE','Median within-grid SD']):
        vals=mainrows.loc[methods,field];bars=ax.bar(methods,vals,color=colors,width=.62);ax.set_title(title,weight='bold');ax.set_ylabel('nm');ax.set_ylim(0,vals.max()*1.25);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+vals.max()*.03,f'{v:.2f}',ha='center',weight='bold',fontsize=12)
    fig.suptitle('One common radial LSC reader | 120 unchanged pairs',fontsize=19,weight='bold',y=.98);fig.text(.5,.03,'All images use the same calculation. No pair removal or nominal-step adjustment.',ha='center',fontsize=10.5);fig.subplots_adjust(left=.055,right=.98,top=.79,bottom=.17,wspace=.3)
    for ext in ['png','svg']:fig.savefig(FIG/f'fair_raw_reconstruction_comparison.{ext}',dpi=240)
    plt.close(fig)
    # Same acquisition windows and display range; images themselves are not altered by reader choice.
    sys.path.insert(0,str(ROOT/'sources'));import run_displacement_lsc as backend
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';fig,axes=plt.subplots(2,2,figsize=(10,9));raw_pixels_identical=[]
    for ri,seq in enumerate(['20x_0p5um','50x_x_0p5um']):
        sp=cfg['sequences'][seq];frame=int(locked[locked.sequence==seq].iloc[0].start_frame_index);raw=backend.load_grayscale(Path(sp['raw_dir'])/f'frame_{frame:04d}.bmp');sub='20x' if sp['magnification']=='20x' else '50x_calibrated';rec=np.load(ROOT/f'results/{sub}/reconstruction/{seq}/frame_{frame:04d}.npz')['output'];pred=backend.session_prediction(seq,frame,np.array(sp['centers'],float),sp['expected_signed_dx_px']);margin=int(np.ceil(.55*sp['pitch_px']))
        x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
        for ci,(name,a) in enumerate([('Raw',raw),('R152',rec)]):
            patch=a[y0:y1,x0:x1];ax=axes[ri,ci];ax.imshow(patch,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.axis('off');ax.set_title(f'{sp["magnification"]} | {name}',fontsize=15);h,w=patch.shape;length=2/sp['object_um_per_px'];xx=w-w*.08-length;yy=h-h*.09;ax.plot([xx,xx+length],[yy,yy],color='white',lw=3);ax.text(xx+length/2,yy-h*.04,'2 um',ha='center',color='white',fontsize=10)
        raw_pixels_identical.append(dict(sequence=seq,frame=frame,source=str(Path(sp['raw_dir'])/f'frame_{frame:04d}.bmp'),crop=[x0,y0,x1,y1],display_range=[0,1],no_raw_degradation=True))
    fig.suptitle('Actual Raw and R152 images | same display settings',fontsize=18,weight='bold',y=.98);fig.text(.5,.018,'First locked pair of each magnification. Same crop, grayscale range and scale bar.',ha='center',fontsize=10.5);fig.subplots_adjust(top=.91,bottom=.055,left=.03,right=.97,hspace=.18,wspace=.08)
    for ext in ['png','svg']:fig.savefig(FIG/f'raw_r152_same_display.{ext}',dpi=240)
    plt.close(fig)
    save(OUT/'figure_provenance.json',raw_pixels_identical)
    report='''# R152 定位與位移讀法改良結果

## 目的與界線

本輪目的是讓定位和位移量測更可靠，不以模型世代比較為目標。Raw、Wiener、R152使用同一算法、同一120配對與同九顆。沒有劣化Raw、改其顯示範圍、刪除不利配對、把九顆位移強制相等，或把讀值拉向名義步距。

## 做了哪些計算改良

保留已修正順序依賴的LSC作初始化，接著從圓心向外取720個均勻方向，在每個方向找正確亮暗方向的梯度峰值，以這些新邊界點重新擬合幾何LSC，重複修正三次。原本沿粗外框不規則法線取64／96點，改為均勻徑向取720點；徑向間距0.05像素，平滑寬度保持0.65像素，搜尋半寬20×2.4像素／50×4像素。最終仍是獨立逐顆LSC圓心。

九顆各自前後水平圓心差取中位數，再取絕對值，維持原步距定義。三項統計定義不改，九顆差異由獨立讀值計算。沒有新增時間平滑、名義步距校正或移動模型影像。

## 如何選方法

- 原LSC、720方向LSC、整體亮度輪廓擬合、前後影像直接配準先在有已知平移量的測試上比較。
- 亮度輪廓擬合在理想圓測試很好，但在R152實拍內容平移時誤差較大，因此未選用。
- 直接配準加入亮度平面後仍讓R152的已知平移誤差變大，因此也未選用；不因它讓某一組表格漂亮而採用。
- 720方向LSC在三方法實拍內容平移中平均誤差都較低，因此在查看新讀法的120組實際結果前鎖定。
- 再用不同影格、不同柱子及不同平移量確認；288個未用來選擇的實拍內容平移測試中，三方法平均誤差均低於原LSC。這是數位平移驗證，不是假稱獨立實體位移真值。

## 同一新讀法下的完整比較

'''+table(s[s.scope.isin(['all120','20x','50x'])])+f'''

R152相對Raw的三項合併數值分別低{relative[FIELDS[0]]:.2f}%、{relative[FIELDS[1]]:.2f}%、{relative[FIELDS[2]]:.2f}%。這是同條件下確實存在的差異，可以呈現；不能把它改寫為獨立絕對準確度。

## 改良讀法本身帶來多少改變

| 方法 | 原LSC步距波動→新讀法 nm | 原LSC名義平均差→新讀法 nm | 原LSC九顆差異→新讀法 nm |
|---|---:|---:|---:|
'''+ '\n'.join(f'| {m} | {old.loc[m,"step_sd_nm_old"]:.6f} → {old.loc[m,"step_sd_nm_new"]:.6f} | {old.loc[m,"nominal_mae_nm_old"]:.6f} → {old.loc[m,"nominal_mae_nm_new"]:.6f} | {old.loc[m,"median_within_grid_sd_nm_old"]:.6f} → {old.loc[m,"median_within_grid_sd_nm_new"]:.6f} |' for m in methods)+'''

R152步距波動幾乎不變、九顆差異略低，但名義平均差略高；Wiener也有退步項。因此這次讀法改良不能說成全面提高實拍三項成績，更沒有把Raw刻意做差。Raw本身也受益，重建相對Raw的差距沒有因換算法而放大。

新讀法保留為經已知位移檢查的研究候選，不自動覆蓋原稿比較或升級正式基準；原稿量測程序已變更，不能把新結果寫成原封不動重現投稿協議。

## 圖文與資料

- `poster_assets/localization_improvement/fair_raw_reconstruction_comparison.png`／`.svg`：同一新讀法下三方法比較。
- `poster_assets/localization_improvement/raw_r152_same_display.png`／`.svg`：同位置、同灰階範圍的Raw與R152實際圖。
- `results/localization_improvement/improved_centers.csv`：4482筆圓心。
- `results/localization_improvement/improved_pairs.csv`：360筆配對，三方法各120對。
- `results/localization_improvement/improvement_comparison.csv`：各條件新舊讀法差異，含不利結果。
- `results/localization_improvement/real_content_known_shifts_fresh.csv`：留出實拍內容的已知移動測試。

來源166張及R152浮點輸出均逐檔核對後使用；最終重新由圓心算位移、由位移算統計，沒有更動模型或正式基準。
'''
    (ROOT/'reports/R152_LOCALIZATION_IMPROVEMENT.md').write_text(report,encoding='utf-8')
    save(OUT/'verification.json',dict(passed=True,all_120_pairs_retained=True,methods=methods,center_rows=4482,pair_rows=360,independent_recomputation_max_difference_nm=maxerr,same_reader_for_all_methods=True,nominal_step_not_used_in_fitting=True,source_results_preserved=True,raw_not_degraded=True,reader_selection_before_real_metrics=True,not_a_claim_of_uniform_metric_improvement=True,not_formally_promoted=True))
    (FIG/'START_HERE.md').write_text('''# 定位改良與公平呈現

- [完整結果及方法限制](../../reports/R152_LOCALIZATION_IMPROVEMENT.md)
- [同讀法三方法比較](fair_raw_reconstruction_comparison.png)
- [Raw與R152相同顯示條件](raw_r152_same_display.png)

這裡呈現真正存在的重建改善；Raw沒有被加模糊、加噪聲、換灰階範圍或使用較差的另一套量測算法。新讀法的退步項也保留在報告。
''',encoding='utf-8')
    print(mainrows.to_string());print('R152_vs_Raw_reduction_pct',relative)
if __name__=='__main__':main()
