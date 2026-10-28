"""Plot only completed 20x results, keeping the unavailable four-condition total explicit."""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
OUT=ROOT/'poster_assets'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
METHODS=['Raw','Wiener','R152'];COLORS=['#7d8792','#ce8430','#18799a']

def main():
    complete=json.loads((ROOT/'results/20x/complete.json').read_text())
    assert complete['state']=='complete_20x_only'
    summary=pd.read_csv(ROOT/'results/20x/summary.csv')
    metrics=[('step_sd_nm','Step variation'),('nominal_mae_nm','Nominal-step error'),('median_within_grid_sd_nm','Within-grid variation')]
    fig,axs=plt.subplots(1,3,figsize=(13.5,4.8),dpi=250)
    g=summary[summary.sequence=='20x_only_two_conditions'].set_index('method')
    for ax,(field,title) in zip(axs,metrics):
        vals=g.loc[METHODS,field].to_numpy();bars=ax.bar(METHODS,vals,color=COLORS,width=.63)
        ax.set_title(title,weight='bold',pad=14);ax.set_ylabel('nm');ax.set_ylim(0,max(vals)*1.27)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        for bar,val in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,val+max(vals)*.035,f'{val:.2f}',ha='center',weight='bold',fontsize=12)
    fig.suptitle('20x only: 60 original locked pairs',fontsize=20,weight='bold',y=.98)
    fig.text(.5,.025,'Two step conditions (0.5 and 1.0 um). Lower values are better. The 50x comparison is pending.',ha='center',fontsize=11)
    fig.subplots_adjust(left=.055,right=.98,top=.78,bottom=.15,wspace=.30)
    for ext in ['png','svg']:fig.savefig(OUT/f'results_20x_only.{ext}')
    plt.close(fig)
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    conf=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'))
    selection=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    fig,axes=plt.subplots(2,3,figsize=(10.5,7.7),dpi=260)
    chosen=[]
    for ridx,seq in enumerate(['20x_0p5um','20x_1um']):
        spec=conf['sequences'][seq]; fi=int(selection[selection.sequence==seq].iloc[0].start_frame_index)
        chosen.append(dict(sequence=seq,frame_index=fi,rule='start frame of first locked pair, chosen without ranking output quality'))
        raw=backend.load_grayscale(Path(spec['raw_dir'])/f'frame_{fi:04d}.bmp')
        recon=np.load(ROOT/f'results/20x/reconstruction/{seq}/frame_{fi:04d}.npz')['output']
        pred=backend.session_prediction(seq,fi,np.array(spec['centers'],float),float(spec['expected_signed_dx_px']))
        pitch=spec['pitch_px'];margin=int(np.ceil(.55*pitch))
        x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1)
        y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
        roi=raw[y0:y1,x0:x1]; psf=backend.loadmat(backend.SWEEP_ROOT/'20x_deconvolution_sweep.mat')['psf']
        images=[roi,backend.wiener_contrast_restore(roi,psf,backend.NSR,pitch_px=pitch),recon[y0:y1,x0:x1]]
        for ci,(method,im) in enumerate(zip(METHODS,images)):
            ax=axes[ridx,ci];ax.imshow(im,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.axis('off')
            ax.set_title(f'{method} | {spec["nominal_step_um"]:.1f} um step',fontsize=12)
            barlen=2/spec['object_um_per_px'];h,w=im.shape;x=w-7-barlen;y=h-8
            ax.plot([x,x+barlen],[y,y],color='white',lw=3);ax.text(x+barlen/2,y-3,'2 um',color='white',ha='center',fontsize=9)
    fig.suptitle('20x: same field, same display range',fontsize=19,weight='bold',y=.985)
    fig.text(.5,.015,'First locked pair in each condition. Display uses a fixed 0-1 range; measurement uses original numeric outputs.',ha='center',fontsize=9)
    fig.subplots_adjust(left=.025,right=.975,top=.9,bottom=.05,wspace=.09,hspace=.18)
    for ext in ['png','svg']:fig.savefig(OUT/f'representative_20x_only.{ext}')
    plt.close(fig)
    (ROOT/'results/20x/figure_selection.json').write_text(json.dumps(chosen,indent=2)+'\n')
    text=['# 20× 已完成結果：海報圖說與用語','',
          '只適用於原投稿中兩組20×條件、共60組鎖定配對；不能稱為四組120配對的R152結果。','',
          '| 方法 | 步距波動 nm | 與名義步距的平均差 nm | 九顆之間的差異 nm |','|---|---:|---:|---:|']
    for m in METHODS:
        r=g.loc[m];text.append(f'| {m} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} | {r.median_within_grid_sd_nm:.6f} |')
    text+=['','## Figure captions','',
       '**Results.** Displacement metrics for the two original 20x conditions (nominal 0.5 and 1.0 micrometer steps; 30 locked pairs each). R152 uses its unchanged delivered weights and native 20x optical bank. Raw, fixed Wiener and R152 share the original measurement backend. Step SD and nominal MAE are averaged across the two conditions; within-grid SD is the median of the 60 pair-level values. This is a 20x-only result; the 50x evaluation remains pending.','',
       '**Representative images.** The start frame of the first locked pair in each 20x condition is shown for all three methods, with a fixed display range and 2 micrometer scale bars. Images were selected by original pair order, without ranking reconstruction quality. Measurements use the original numeric outputs rather than the displayed images.','',
       '## 範圍限制','',
       '- 圖表如有不利於R152的結果照實保留；不能只用影像較銳利主張位移較準。',
       '- 沒有重新訓練、調整交付倍率、換20×光學資料、重選配對或改量測方法。',
       '- 尚未進行本次R152的完整跨倍率比較，也未據此宣稱獨立絕對準確度。']
    (OUT/'RESULTS_20X_TEXT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(g.to_string())

if __name__=='__main__':main()
