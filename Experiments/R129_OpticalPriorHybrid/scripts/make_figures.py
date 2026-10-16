"""Source-backed scientific figures; all 36 objects contribute to summaries."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *
import numpy as np,pandas as pd,cv2
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft JhengHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
from verify_pilot import least_squares

def main():
    out=ROOT/'results/figures';out.mkdir(exist_ok=False)
    historical=R128/'results/thesis_v34_review_20260912/normal_sem_fine_v2'
    old=pd.read_csv(historical/'summary.csv').set_index('method')
    shape=pd.read_csv(historical/'radius_vs_shape_summary.csv').set_index('method')
    current=pd.read_csv(ROOT/'results/sem/summary.csv').set_index('tag')
    labels=['原始影像','V42（既有）','R128（既有）','同底版對照 A','保留兩項設計 D']
    colors=['#9ba5ad','#6f9cb0','#507cad','#aaa2c7','#db885a']
    metrics=[('radial_nm','radial_shape_mae_nm','輪廓半徑誤差（奈米，越低越好）'),('correlation','contour_correlation','細部形狀相關（越高越好）'),('centered_shape_nm','centered_shape_mae_nm','扣除平均尺寸後的形狀誤差（奈米）'),('MZC_error_nm','mzc_roundness_abs_error_nm','非圓程度與 SEM 的差距（奈米）')]
    fig,axes=plt.subplots(2,2,figsize=(13,8.5),layout='constrained')
    for ax,(newkey,oldkey,title) in zip(axes.flat,metrics):
        source=shape if oldkey=='centered_shape_mae_nm' else old
        values=[source.loc[k,oldkey] for k in ['Raw','MOSR_V42','R128']]+[current.loc[k,newkey] for k in ['A_24','D_24']]
        bars=ax.bar(labels,values,color=colors,width=.65);ax.bar_label(bars,fmt='%.3f' if newkey=='correlation' else '%.2f',padding=3,fontsize=11)
        ax.set_title(title,fontsize=13);ax.set_ylim(0,max(values)*1.20);ax.tick_params(axis='x',labelsize=10)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('R129 短程接入測試：已有作用，但還未超過既有模型\n36 顆柱子 × 正常曝光 13–15；每顆跨曝光取中位數，再跨柱取中位數',fontsize=16)
    fig.savefig(out/'normal_sem_comparison.png',dpi=160);plt.close(fig)

    oldcells=loadmat(historical/'input_cells.mat',variable_names=['raw_cells','r128_cells'])
    newcells=loadmat(ROOT/'results/sem/masks_cells.mat',variable_names=['cells'])['cells']
    truth=loadmat(ROOT.parent/'R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat',variable_names=['truth_cells'])['truth_cells']
    oldpts=np.load(historical/'boundary_points.npz');newpts=np.load(ROOT/'results/sem/boundary_points.npz')
    pid=18;exposure=14 # Fixed central index, not selected for a favorable result.
    cases=load(ROOT/'results/real_inference.json')['sem_images']
    index={(x['tag'],x['exposure']):i for i,x in enumerate(cases)}
    images=[truth[:,:,pid-1],oldcells['raw_cells'][:,:,pid-1,1],oldcells['r128_cells'][:,:,pid-1,1],newcells[:,:,pid-1,index[('D_24',14)]]]
    names=['SEM 參考','原始顯微影像','既有 R128','R129：兩項設計皆保留']
    points=[newpts[f'SEM_{pid}'],oldpts[f'Raw_{exposure}_{pid}'],oldpts[f'R128_{exposure}_{pid}'],newpts[f'D_24_{exposure}_{pid}']]
    fig,axes=plt.subplots(1,4,figsize=(12,3.6),layout='constrained')
    for ax,im,name,pt in zip(axes,images,names,points):
        ax.imshow(im,cmap='gray',vmin=0,vmax=255);ax.plot(*np.vstack([pt,pt[0]]).T,color='#ffb657',linewidth=.8);ax.set_title(name);ax.set_xlim(6,98);ax.set_ylim(98,6);ax.axis('off')
    fig.suptitle('第 18 顆柱子、曝光 14：同一取邊方式；每格依歷史規則調整對比\n示意影像不能代替全部柱子的量測，也不代表獨立未知樣本',fontsize=12)
    fig.savefig(out/'pillar18_example.png',dpi=180);plt.close(fig)
    assert np.array_equal(cv2.imread(str(ROOT/'results/cli_smoke/sem14.png'),0),cv2.imread(str(ROOT/'results/real/D_24/sem14.png'),0))
    save(ROOT/'results/figure_sources.json',dict(created_utc=now(),source=record(__file__),historical_summary=record(historical/'summary.csv'),historical_shape=record(historical/'radius_vs_shape_summary.csv'),current_summary=record(ROOT/'results/sem/summary.csv'),figures=[record(x) for x in out.glob('*.png')],CLI_sem14_matches_recorded_output_exactly=True,example_selection='fixed pillar 18/exposure14, not a favorable-result selection'))
    print('Two figures created; public CLI output exactly matches the recorded image')

if __name__=='__main__':main()
