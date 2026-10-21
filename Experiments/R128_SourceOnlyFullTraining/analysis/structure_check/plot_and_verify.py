"""Export source-backed findings and preserve all original diagnostic flags."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import crossings
from evaluation.real import read_image
from exact_contour_check import segments,queries,nearest
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');inf=load(out/'inference.json');real=load(out/'real_summary.json');controls=load(out/'controls.json');exact=load(out/'exact_contour_geometry.json');follow=load(out/'flag_followup.json')
    sources={x['key']:x for x in plan['sources']};outputs={x['key']:x['output'] for x in inf['outputs']};features={x['id']:x for x in plan['features']};cache={}
    def images(key):
        if key not in cache:
            raw=read_image(sources[key]['source']);p=outputs[key]
            with np.load(p['path']) as f:pred=f['output']
            cache[key]=(raw,pred)
        return cache[key]
    profiles=load(out/'real_profiles.json');expanded=[]
    for flag in profiles:
        if flag['equal_counts_and_directions']:continue
        feature=features[flag['id']];raw,pred=images(feature['source_key']);x0,y0,x1,y1=feature['box'];axis=0 if feature['profile_axis']=='x' else 1
        old=[np.median(a[y0:y1,x0:x1],axis=axis) for a in [raw,pred]]
        limits=[]
        for i,p in enumerate(old):
            origin=p if i==0 or flag['mode']=='self_normalized' else old[0];lo,hi=np.quantile(origin,[.1,.9]);limits.append(lo+flag['level']*(hi-lo))
        if axis==0:large=[np.median(a[y0:y1,x0-16:x1+16],axis=0) for a in [raw,pred]]
        else:large=[np.median(a[y0-16:y1+16,x0:x1],axis=1) for a in [raw,pred]]
        a,da=crossings(large[0],limits[0]);b,db=crossings(large[1],limits[1])
        match=len(a)==len(b) and np.array_equal(da,db)
        entering=[];exiting=[]
        if match:
            for x,y in zip(a-16,b-16):
                xin=0<=x<len(old[0])-1;yin=0<=y<len(old[0])-1
                if xin and not yin:exiting.append([float(x),float(y)])
                if yin and not xin:entering.append([float(x),float(y)])
        explained=bool(match and len(exiting)-len(entering)==flag['Raw_crossings']-flag['candidate_crossings'])
        expanded.append(dict(id=flag['id'],mode=flag['mode'],level=flag['level'],original_counts=[flag['Raw_crossings'],flag['candidate_crossings']],expanded_counts=[len(a),len(b)],exiting=exiting,entering=entering,original_count_difference_explained_by_endpoints=explained))
    save(out/'all_profile_flag_expansions.json',expanded)
    # Include every clean control with its input contrast; weak and strong
    # signals must not be pooled into an unexplained worst-case headline.
    clean=[]
    for row in exact['rows']:
        if row['category']!='clean_identity':continue
        with np.load(out/'controls'/row['parent_id']/'core.npz') as f:target=f['target']
        levels=np.unique(target)*255
        clean.append(dict(parent=row['parent_id'],low_gray=float(levels.min()),high_gray=float(levels.max()),contrast_gray=float(levels.max()-levels.min()),**row['candidate']))
    pd.DataFrame(clean).to_csv(out/'clean_control_geometry.csv',index=False)
    contract=dict(surface='local scientific PNG figures',families=['same-source image comparison','one-dimensional line profile'],question='What changes after restoration, and which flags are measurement/crop artifacts?',palette='blue original/reference, orange dashed candidate, grayscale images',selection='Full clean-control table retained; illustrative high-contrast control0061and largest declared real corner-readout change; fixed real profile50x_1um_h0',scope='Diagnostic source-relative image readouts; no physical geometry truth inferred for real frames')
    save(out/'chart_contract.json',contract)
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei';figdir=ROOT/'reports/figures';figdir.mkdir(exist_ok=True)
    row=next(x for x in controls if x['parent_id']=='r128_test_0061');level=row['threshold_gray']/255
    with np.load(out/'full_context_controls/r128_test_0061/images.npz') as f:target=f['target'];pred=f['output']
    a,b=segments(target,level);c,d=segments(pred,level);q,_=queries(a,b,.05);mask=np.all((q>=32)&(q<160),axis=1);q=q[mask];error=nearest(q,c,d);point=q[error.argmax()];x,y=np.rint(point).astype(int);radius=7
    fig,axes=plt.subplots(1,3,figsize=(11,4))
    for ax,im,title in zip(axes[:2],[target,pred],['已知清楚答案＝原圖','模型修復後']):
        ax.imshow(im[32:160,32:160],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(title);ax.set_xticks([]);ax.set_yticks([])
    ax=axes[2];ax.imshow(target,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.contour(target,[level],colors=['#356DA8'],linewidths=1.6);ax.contour(pred,[level],colors=['#D38638'],linewidths=1.6,linestyles='--');ax.set_xlim(x-radius,x+radius);ax.set_ylim(y+radius,y-radius);ax.set_title('局部邊界放大');ax.set_xlabel('影像像素位置')
    fig.suptitle('清楚且對比明顯的控制影像',fontsize=15)
    fig.text(.5,.025,'控制0061，兩側灰階97與203；藍線為已知答案，橙虛線為模型半對比輪廓。未重新訓練。',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.08,1,.91]);fig.savefig(figdir/'structure_clean_control.png',dpi=160);plt.close(fig)
    with np.load(out/'profiles.npz') as f:a=f['50x_1um_h0_Raw'];b=f['50x_1um_h0_candidate']
    fig,ax=plt.subplots(figsize=(10,4));xx=np.arange(160);ax.plot(xx,a[:160]*255,color='#356DA8',label='原圖',lw=1.7);ax.plot(xx,b[:160]*255,color='#D38638',label='模型',ls='--',lw=1.7);threshold=float(np.mean(np.quantile(a,[.1,.9]))*255);ax.axhline(threshold,color='#555555',lw=.8,ls=':')
    ax.set_title('實拍水平線條的亮度剖面');ax.set_xlabel('沿影像垂直方向的位置（像素）');ax.set_ylabel('灰階');ax.legend(frameon=False);ax.spines[['top','right']].set_visible(False)
    fig.text(.5,.015,'固定原圖選區，21列中位數剖面；位置與寬度是影像讀值，尚非独立材料真值。',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.05,1,1]);fig.savefig(figdir/'structure_real_line_profile.png',dpi=160);plt.close(fig)
    corners=pd.read_csv(out/'real_corners.csv');worst=corners.sort_values('change_px',ascending=False).iloc[0];raw,pred=images(worst.source_key);x,y=int(round(worst.Raw_x)),int(round(worst.Raw_y));radius=18
    fig,axes=plt.subplots(1,2,figsize=(8,4.5));lo,hi=np.quantile(raw[y-radius:y+radius,x-radius:x+radius],[.02,.98])
    for ax,im,title in zip(axes,[raw,pred],['原圖','模型修復後']):
        ax.imshow(im,cmap='gray',vmin=lo,vmax=hi,interpolation='nearest');ax.scatter([worst.Raw_x],[worst.Raw_y],marker='o',facecolors='none',edgecolors='#356DA8',s=90,label='原圖讀值');ax.scatter([worst.candidate_x],[worst.candidate_y],marker='x',color='#D38638',s=90,label='模型讀值');ax.set_xlim(x-radius,x+radius);ax.set_ylim(y+radius,y-radius);ax.set_title(title)
    axes[1].legend(loc='lower right',fontsize=9);fig.suptitle('取樣窗口下的角點讀值差異',fontsize=15)
    fig.text(.5,.025,'同一個原圖選定角點，窗口半寬5；改用其他窗口結果會變，不能將差異直接稱為物體位移。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.08,1,.92]);fig.savefig(figdir/'structure_corner_readout.png',dpi=160);plt.close(fig)
    save(out/'review_summary.json',dict(completed=True,real=real,exact_control_summary=exact['summary'],profile_count_flags=len(expanded),profile_flags_explained_by_endpoints=sum(x['original_count_difference_explained_by_endpoints'] for x in expanded),clean_control_rows=clean,topology_crop_diagnosis=follow['topology_crop_diagnosis'],continued_candidate='P_s1285002',production_adopted=False,priority='Preserve already-sharp boundaries and validate local geometric readouts, not broaden exposure range',source=record(__file__)))
    print(json.dumps(dict(profile_flags=len(expanded),explained=sum(x['original_count_difference_explained_by_endpoints'] for x in expanded),clean_controls=clean)),flush=True)

if __name__=='__main__':main()
