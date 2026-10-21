import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *

def main():
    root=ROOT/'results/phase_anatomy_initial';d=json.loads((root/'summary.json').read_text());lookup={(r['sequence'],r['kind']):r for r in d['rows']}
    with np.load(root/'surfaces.npz') as a:surfaces={k:a[k]/16384 for k in a.files}
    fig,axes=plt.subplots(2,2,figsize=(8,7))
    for r,name in enumerate(['20x_1um','50x_0p5um']):
        scale=max(float(np.max(np.abs(surfaces[f'{name}_{kind}']))) for kind in ['Raw','candidate'])
        for c,kind in enumerate(['Raw','candidate']):
            ax=axes[r,c];record=lookup[name,kind]
            ax.imshow(surfaces[f'{name}_{kind}'][::-1,::-1],origin='lower',extent=(-63.5,64.5,-63.5,64.5),cmap='coolwarm',vmin=-scale,vmax=scale,interpolation='nearest')
            dx,dy=record['integer_peak_shift_xy'];ax.plot(dx,dy,'o',mfc='none',mec='black',ms=13,mew=1.8)
            ax.set_title(f'{name} / {kind}\nPeak ({dx:.0f},{dy:.0f}); response {record["opencv_response"]:.3f}',fontsize=10)
            ax.set(xlim=(-24,8),ylim=(-24,8),xlabel='Candidate horizontal shift (px)',ylabel='Candidate vertical shift (px)')
    fig.suptitle('Matching selects different peaks before neural training\nSame six-pair panel; two failed cases shown; no physical stage truth',fontsize=11)
    fig.tight_layout();fig.savefig(ROOT/'reports/figures/phase_peak_switch.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
