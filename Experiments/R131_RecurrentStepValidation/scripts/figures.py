"""Source-backed figures; fixed pillar18/exposure14, no best-looking selection."""
from study import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import loadmat
plt.rcParams.update({'font.family':'Microsoft JhengHei','axes.unicode_minus':False,'font.size':10})

def main():
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    table=pd.read_csv(ROOT/'results/sem/summary.csv');fig,axes=plt.subplots(1,3,figsize=(12,3.5),constrained_layout=True)
    for ax,key,title in zip(axes,['centered_shape_nm','diameter_error_nm','radial_nm'],['細形狀差距','尺寸差距','整體輪廓差距']):
        ax.plot(table.step,table[key],'o-',color='#2b758e');ax.set_title(title+'（越低越好）');ax.set_xlabel('修復次數');ax.set_ylabel('奈米');ax.set_xticks(range(5));ax.grid(alpha=.2)
        for row in table.itertuples():ax.annotate(f'{getattr(row,key):.2f}',(row.step,getattr(row,key)),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
        ax.margins(y=.2)
    fig.suptitle('同一模型、同一批36顆柱體／3張正常曝光；零次保留光學與最後輸出處理',fontsize=11)
    fig.savefig(out/'sem_steps.png',dpi=160);plt.close(fig)
    ref=loadmat(PKG/'validation/sem_reference.mat');gy,gx=np.argwhere(ref['global_index']==18)[0];center=ref['opt_centers'][int(gy)*6+int(gx)];cx,cy=map(lambda v:int(np.floor(v+.5))-1,center)
    raw=cv2.imread(str(PKG/'validation/inputs/sem14.png'),0);series=[('原圖',raw)]+[(f'{n}次修復',cv2.imread(str(ROOT/f'results/sem/N{n}/sem14.png'),0)) for n in range(5)]
    fig,axes=plt.subplots(1,6,figsize=(13,2.8),constrained_layout=True)
    for ax,(name,image) in zip(axes,series):
        ax.imshow(image[cy-52:cy+52,cx-52:cx+52],cmap='gray',vmin=0,vmax=255,interpolation='nearest');ax.set_title(name);ax.axis('off')
    fig.suptitle('固定第18顆、曝光14；全部使用相同灰階顯示，不各自拉高對比',fontsize=11)
    fig.savefig(out/'pillar18_steps.png',dpi=180);plt.close(fig)
    points=np.load(ROOT/'results/sem/points.npz');from analyze import circle,signature
    truth=points['SEM_18'];tc,tr=circle(truth);target=signature(truth,tc);scale=load(ROOT/'results/sem/complete.json')['scale_nm_per_px']
    fig,ax=plt.subplots(figsize=(9,3.4),constrained_layout=True);theta=np.arange(720)*.5
    ax.plot(theta,(target-target.mean())*scale,color='black',lw=2,label='SEM參考')
    for n in range(1,5):
        xy=points[f'N{n}_14_18'];c,r=circle(xy);a=signature(xy,c);ax.plot(theta,(a-a.mean())*scale,label=f'{n}次修復',alpha=.8)
    ax.set(xlabel='沿柱體一圈的角度',ylabel='扣除平均大小後的起伏（奈米）',title='固定同一顆：細部起伏是否接近實際SEM，而非是否變圓');ax.legend(ncol=5);ax.grid(alpha=.2)
    fig.savefig(out/'pillar18_shape.png',dpi=160);plt.close(fig)
    if (ROOT/'results/motion_summary.csv').exists():
        t=pd.read_csv(ROOT/'results/motion_summary.csv');t=t[t.scope=='all_four_sequences']
        fig,axes=plt.subplots(1,3,figsize=(12,3.5),constrained_layout=True)
        for ax,k,title in zip(axes,['step_sd_nm','median_within_grid_sd_nm','median_cross_axis_abs_nm'],['步距波動','九柱位移不一致','橫向偏移']):
            for pop,g in t.groupby('population'):ax.plot(g.step,g[k],'o-',label='固定120對' if pop=='locked120' else '完整194對')
            ax.set(xlabel='修復次數',ylabel='奈米',title=title+'（越低越好）');ax.set_xticks(range(5));ax.grid(alpha=.2);ax.legend()
        fig.suptitle('全部201張原生影像，原先記錄的3次重新定位另列',fontsize=11);fig.savefig(out/'motion_steps.png',dpi=160);plt.close(fig)
    print('Figures generated',flush=True)
if __name__=='__main__':main()
