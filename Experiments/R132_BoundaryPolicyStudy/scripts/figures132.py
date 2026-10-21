from common132 import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft JhengHei','axes.unicode_minus':False,'font.size':10})

def main():
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    t=pd.read_csv(ROOT/'results/all_sem/summary.csv');t=t[t.population=='all36'].sort_values('width')
    fig,axes=plt.subplots(1,3,figsize=(12,3.5),constrained_layout=True)
    for ax,key,title in zip(axes,['centered_shape_nm','MZC_error_nm','diameter_error_nm'],['細形狀差距','非圓起伏差距','尺寸差距']):
        ax.plot(t.width,t[key],'o-',color='#2b758e');ax.set(title=title+'（越低越好）',xlabel='保留原圖的寬度（像素）',ylabel='奈米');ax.set_xticks([0,16,32,64,80]);ax.grid(alpha=.2);ax.margins(y=.25)
        for row in t.itertuples():ax.annotate(f'{getattr(row,key):.2f}',(row.width,getattr(row,key)),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    fig.suptitle('只改最後的保留帶，同一R129、同一批36顆／3張正常曝光；0代表完全不保留',fontsize=11)
    fig.savefig(out/'guard_tradeoff.png',dpi=170);plt.close(fig)
    ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['global_index','opt_centers']);gy,gx=np.argwhere(ref['global_index']==18)[0];c=ref['opt_centers'][int(gy)*6+int(gx)];cx,cy=[int(np.floor(v+.5))-1 for v in c];sl=np.s_[cy-52:cy+52,cx-52:cx+52]
    raw=cv2.imread(str(PKG/'validation/inputs/sem14.png'),0);items=[('原圖',raw)]+[(f'保留{w}像素' if w else '不保留',cv2.imread(str(ROOT/f'results/sem_cases/full_e14_W{w}.png'),0)) for w in WIDTHS]
    fig,axes=plt.subplots(1,6,figsize=(13,2.8),constrained_layout=True)
    for ax,(label,image) in zip(axes,items):ax.imshow(image[sl],cmap='gray',vmin=0,vmax=255,interpolation='nearest');ax.set_title(label);ax.axis('off')
    fig.suptitle('同一第18顆、曝光14：保留帶縮小後，左側的重建真正顯示出來',fontsize=11);fig.savefig(out/'pillar18_guard.png',dpi=180);plt.close(fig)
    ctx=pd.read_csv(ROOT/'results/all_sem/context_measurements.csv');g=ctx.groupby(['margin','width']).centered_shape_nm.median().reset_index()
    fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
    for width,s in g.groupby('width'):ax.plot(s.margin,s.centered_shape_nm,'o-',label='不保留' if width==0 else f'保留{width}像素')
    ax.set(xlabel='量測窗口左側額外保留的真實影像（像素）',ylabel='同顆細形狀差距（奈米）',title='同一中央柱體改變裁切邊距；不是不同樣品');ax.set_xticks([0,16,32,64,96]);ax.grid(alpha=.2);ax.legend(ncol=2)
    fig.savefig(out/'context_tradeoff.png',dpi=170);plt.close(fig)
    m=pd.read_csv(ROOT/'results/motion_summary.csv');m=m[m.scope=='all_four_sequences'];fig,axes=plt.subplots(1,2,figsize=(9,3.5),constrained_layout=True)
    for ax,key,title in zip(axes,['step_sd_nm','median_within_grid_sd_nm'],['步距波動','九柱位移不一致']):
        for pop,s in m.groupby('population'):
            s=s.sort_values('width');ax.plot(s.width,s[key],'o-',label='固定120對' if pop=='locked120' else '完整194對')
        ax.set(title=title,xlabel='保留帶寬度（像素）',ylabel='奈米');ax.set_xticks([0,16,32,64,80]);ax.grid(alpha=.2);ax.legend()
    fig.savefig(out/'motion_guard.png',dpi=170);plt.close(fig);print('R132 figures generated',flush=True)
if __name__=='__main__':main()
