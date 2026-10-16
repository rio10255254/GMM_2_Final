"""Explain the fixed gallery pillar's spatially partial reconstruction, read-only model."""
from study import *
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams.update({'font.family':'Microsoft JhengHei','axes.unicode_minus':False,'font.size':10})

def main():
    out=ROOT/'results/edge_diagnostic';out.mkdir(exist_ok=False);verify_sources();m=model();digest=runtime.state_digest(m)
    ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['global_index','opt_centers'])
    lookup={int(ref['global_index'][gy,gx]):ref['opt_centers'][gy*6+gx] for gy in range(6) for gx in range(6)}
    before=[rec(ROOT/'reports/figures/pillar18_steps.png'),rec(ROOT/'results/sem/summary.csv'),rec(ROOT/'results/published.json')]
    records=[];coverage=[];cache={}
    for exposure in [13,14,15]:
        path=PKG/f'validation/inputs/sem{exposure}.png';raw,x=tensor(path)
        with torch.no_grad():unprotected=original_predict(m,x);protected=guard(x,unprotected)
        pred=unprotected[0,0].cpu().numpy();actual=protected[0,0].cpu().numpy();base=raw.astype(np.float32)/255
        old=np.load(ROOT/f'results/sem/N4/sem{exposure}.npy')
        assert np.array_equal(actual,old),'Existing output not reproduced'
        image=np.rint(actual*255).clip(0,255).astype(np.uint8);ung=np.rint(pred*255).clip(0,255).astype(np.uint8)
        assert np.array_equal(image,cv2.imread(str(ROOT/f'results/sem/N4/sem{exposure}.png'),0))
        h,w=raw.shape;yy,xx=np.mgrid[:h,:w];d=np.minimum.reduce([xx,yy,w-1-xx,h-1-yy]);weight=np.clip((d-80)/16,0,1)
        independent=base+(pred-base)*weight.astype(np.float32)
        assert np.array_equal(independent,actual)
        assert np.array_equal(image[weight==0],raw[weight==0])
        np.savez_compressed(out/f'exposure{exposure}.npz',raw=raw,pre_guard=pred,guarded=actual,weight=weight.astype(np.float32))
        assert cv2.imwrite(str(out/f'exposure{exposure}_before_guard_diagnostic.png'),ung)
        for pid,c in lookup.items():
            cx,cy=[int(np.floor(v+.5))-1 for v in c];sl=np.s_[cy-52:cy+52,cx-52:cx+52];wg=weight[sl];a=actual[sl];p=pred[sl];b=base[sl]
            coverage.append(dict(exposure=exposure,pillar=pid,cx=cx,cy=cy,crop_x0=cx-52,crop_x1_exclusive=cx+52,
                                 raw_retained_fraction=float((wg==0).mean()),transition_fraction=float(((wg>0)&(wg<1)).mean()),full_model_fraction=float((wg==1).mean()),
                                 retained_pixel_difference_max_gray=float(abs(a[wg==0]-b[wg==0]).max()*255) if (wg==0).any() else 0.,
                                 discarded_model_change_mean_gray=float(abs(p[wg==0]-b[wg==0]).mean()*255) if (wg==0).any() else 0.,
                                 crop_actual_change_mean_gray=float(abs(a-b).mean()*255),crop_pre_guard_change_mean_gray=float(abs(p-b).mean()*255)))
        records.append(dict(exposure=exposure,source=rec(path),existing_float_exact=True,existing_PNG_exact=True,independent_guard_exact=True))
        if exposure==14:cache=dict(raw=raw,pred=ung,actual=image,weight=weight)
    table=pd.DataFrame(coverage);table.to_csv(out/'all36_crop_coverage.csv',index=False)
    focus=table[table.pillar==18];inner=table[table.pillar==16]
    assert (focus.retained_pixel_difference_max_gray==0).all()
    assert (focus.discarded_model_change_mean_gray>0).all()
    assert (inner.full_model_fraction==1).all()
    fig,axes=plt.subplots(2,4,figsize=(12,6.4),constrained_layout=True)
    for row,pid in enumerate([18,16]):
        cx,cy=[int(np.floor(v+.5))-1 for v in lookup[pid]];sl=np.s_[cy-52:cy+52,cx-52:cx+52]
        for col,(key,title) in enumerate([('raw','原圖'),('actual','實際交付影像'),('pred','最後保護前：僅供診斷')]):
            axes[row,col].imshow(cache[key][sl],cmap='gray',vmin=0,vmax=255,interpolation='nearest');axes[row,col].set_title(title);axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
        axes[row,0].set_ylabel(f'第{pid}顆\n'+('靠近影像左側' if pid==18 else '完整位於中央'))
        im=axes[row,3].imshow(cache['weight'][sl],vmin=0,vmax=1,cmap='RdYlGn',interpolation='nearest');axes[row,3].set_title('實際採用模型的比例');axes[row,3].set_xticks([]);axes[row,3].set_yticks([])
        cbar=fig.colorbar(im,ax=axes[row,3],fraction=.046);cbar.set_ticks([0,.5,1]);cbar.set_ticklabels(['保留原圖','混合','使用模型'])
    fig.suptitle('半邊模糊的直接原因：最後的影像邊界保護；同一曝光14、相同灰階範圍',fontsize=13)
    fig.savefig(out/'half_image_explained.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,7),constrained_layout=True);ax.imshow(cache['raw'],cmap='gray',vmin=0,vmax=255)
    h,w=cache['raw'].shape
    ax.add_patch(Rectangle((80,80),w-161,h-161,fill=False,ec='#e45858',lw=2,label='紅框外：保留原圖'))
    ax.add_patch(Rectangle((96,96),w-193,h-193,fill=False,ec='#39b86a',lw=2,label='綠框內：完整使用模型'))
    for pid,color in [(18,'#ffd24a'),(16,'#35bdfa')]:
        cx,cy=[int(np.floor(v+.5))-1 for v in lookup[pid]];ax.add_patch(Rectangle((cx-52,cy-52),104,104,fill=False,ec=color,lw=2));ax.text(cx,cy-60,f'第{pid}顆',color=color,ha='center',weight='bold')
    ax.set_title('展示的第18顆跨過保留帶，中央第16顆沒有');ax.axis('off');ax.legend(loc='lower center')
    fig.savefig(out/'full_field_location.png',dpi=150);plt.close(fig)
    assert runtime.state_digest(m)==digest;verify_sources()
    for p in before:assert sha(p['path'])==p['sha256']
    conclusion=dict(created_utc=now(),images=records,pillar18=focus.to_dict('records'),pillar16=inner.to_dict('records'),
                    all36_counts=table.groupby('exposure').apply(lambda t:dict(fully_model_crops=int((t.full_model_fraction==1).sum()),partly_retained_crops=int((t.raw_retained_fraction>0).sum())),include_groups=False).to_dict(),
                    explanation='The gallery pillar18 lies across the left FOV guard: much of its crop is replaced exactly by Raw. The network made nonzero corrections there before the guard. This is not a missing left-half neural forward.',
                    scope='Direct explanation of the shown pillar18; not a guarantee every directional blur has this cause. Pre-guard outputs are diagnostic only, not qualified deployment replacements.',
                    original_figures_metrics_weights_unchanged=True,source=rec(__file__))
    save(out/'verified.json',conclusion)
    print(focus.to_string(index=False));print(conclusion['all36_counts'],flush=True)

if __name__=='__main__':main()
