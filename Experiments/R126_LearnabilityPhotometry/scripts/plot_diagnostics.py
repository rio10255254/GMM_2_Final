"""Static scientific figures from recorded measurements; no image enhancement."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *

def main():
    out=ROOT/'reports/figures';out.mkdir(parents=True,exist_ok=True)
    a=json.loads((ROOT/'results/fixed_example_summary.json').read_text());b=json.loads((ROOT/'results/update_scale_summary.json').read_text())
    runs={r['run_id']:r for r in a['runs']+b['runs']}
    fig,ax=plt.subplots(figsize=(8,4.8));x=np.arange(2);width=.24
    values=[[runs[f'fixed_{arm}_full']['before']['native_mae_gray'] for arm in ['A','B']],[runs[f'fixed_{arm}_full']['after']['native_mae_gray'] for arm in ['A','B']],[runs[f'fixed_{arm}_full_lr001']['after']['native_mae_gray'] for arm in ['A','B']]]
    for i,(label,v,color) in enumerate(zip(['Initial','128 updates, original rate','128 updates, adjusted rate'],values,['#999999','#b28151','#346d8d'])):
        bars=ax.bar(x+(i-1)*width,v,width,color=color,label=label);ax.bar_label(bars,fmt='%.3f',fontsize=9,padding=3)
    ax.set_xticks(x,['A: learned correction','B: learned + observation correction']);ax.set_ylabel('Native reference MAE (gray levels)');ax.set_ylim(0,3.8);ax.legend(loc='upper right',fontsize=8)
    ax.set_title('Same fixed example, model, initial weights and full objective\nChanging update scale improves learning; not real-world efficacy',fontsize=11);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(out/'fixed_learning.png',dpi=170);plt.close(fig)
    rows=json.loads((ROOT/'results/photometry_admission.json').read_text())['rows'];real=json.loads((R125/'results/real_photometry_scope.json').read_text())['real_summary']
    fig,ax=plt.subplots(figsize=(7.2,6))
    for flag,color,label in [(False,'#a1a1a1','Original target settings'),(True,'#32698c','Expanded target settings')]:
        chosen=[r for r in rows if r['expanded']==flag and r['category']!='flat_negative'];ax.scatter([r['plateaus_gray'][0] for r in chosen],[r['plateaus_gray'][1] for r in chosen],s=20,alpha=.6,c=color,label=label)
    for row,mark,col in zip(real,['*','D'],['#bb573e','#a77230']):
        ax.scatter(row['median_low_gray'],row['median_high_gray'],s=130,marker=mark,c=col,edgecolors='black',label=f"Real exposure{row['exposure']} median")
    ax.plot([0,255],[0,255],':',color='.6');ax.set(xlim=(0,255),ylim=(0,255),xlabel='Low plateau / gray',ylabel='High plateau / gray');ax.set_aspect('equal');ax.legend(fontsize=8,loc='lower right');ax.grid(alpha=.2);ax.set_title('Brightness and contrast coverage\nTarget settings vs camera readouts: coverage warning, not calibration',fontsize=10);fig.tight_layout();fig.savefig(out/'photometry_coverage.png',dpi=170);plt.close(fig)
    names=['fixed_A_full','fixed_A_full_lr001','fixed_B_full','fixed_B_full_lr001'];arrays=[]
    for name in names:
        with np.load(ROOT/'runs'/name/'outputs.npz') as d:arrays.append({k:d[k] for k in d.files})
    fig,axs=plt.subplots(2,3,figsize=(9,6));panels=[('Input',arrays[0]['source'][0]/255),('Reference',arrays[0]['target'][0]),('A original rate',arrays[0]['output'][0]),('A adjusted rate',arrays[1]['output'][0]),('B original rate',arrays[2]['output'][0]),('B adjusted rate',arrays[3]['output'][0])]
    for ax,(name,v) in zip(axs.flat,panels):ax.imshow(v,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(name,fontsize=10);ax.axis('off')
    fig.suptitle('Complete fixed64px example, same brightness scale\nGenerated diagnostic only; no real image shown here',fontsize=12);fig.tight_layout();fig.savefig(out/'fixed_example_images.png',dpi=170);plt.close(fig)
    print(out)

if __name__=='__main__':main()
