"""Produce an explicitly incomplete, evidence-backed method asset; no new result claims."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'poster_assets'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(14,7),dpi=220)
fig.patch.set_facecolor('#f5f7fb');ax.set_facecolor('#f5f7fb')
ax.set(xlim=(0,14),ylim=(0,7));ax.axis('off')
ax.text(.45,6.58,'R152 evaluation on the locked IMPACT protocol',fontsize=22,weight='bold',color='#17334e')
ax.text(.45,6.12,'METHOD PREPARATION  |  Cross-magnification R152 results are pending',fontsize=12,color='#9e4c12')
def box(x,y,w,h,title,detail,color='#dce9f4'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08,rounding_size=0.12',fc=color,ec='#a9bac8',lw=1))
    ax.text(x+.2,y+h-.35,title,fontsize=13,weight='bold',va='top',color='#17334e')
    ax.text(x+.2,y+h-.83,detail,fontsize=11.5,va='top',linespacing=1.6,color='#273c4f')
box(.45,3.52,3.65,2.13,'FIXED INPUTS','20x / 50x; 0.5 / 1.0 um\n30 adjacent pairs per condition\n120 pairs; 166 distinct frames\nSame nine pillars; native grid')
box(5.0,3.52,3.8,2.13,'THREE IMAGE METHODS','Raw\nFixed Wiener: original optics\nR152: delivered weights fixed\n50x R152 optics: unresolved','#fff0d8')
box(9.65,3.52,3.88,2.13,'ONE MEASUREMENT METHOD','Coarse contour\nNormal-profile gradient maximum\nSubpixel boundary points\nGeometric least-squares centers')
for a,b in [(4.2,4.87),(8.9,9.51)]:
    ax.annotate('',xy=(b,4.57),xytext=(a,4.57),arrowprops={'arrowstyle':'->','lw':2,'color':'#385d7c'})
ax.annotate('',xy=(11.58,2.89),xytext=(11.58,3.39),arrowprops={'arrowstyle':'->','lw':2,'color':'#385d7c'})
box(.45,1.15,13.08,1.65,'THREE SEPARATE STATISTICS',
    'Step SD: mean of four condition-level step standard deviations\n'
    'Nominal MAE: mean of four condition-level absolute errors from the nominal step\n'
    'Within-grid SD: median of 120 pair-level standard deviations across nine pillars','#e2eee8')
ax.text(.45,.55,'No model retraining. No pair reselection. No substitution of the missing 50x optical bank.',fontsize=11,color='#485967')
fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
for ext in ['png','svg']:fig.savefig(OUT/f'method_protocol_pending.{ext}',facecolor=fig.get_facecolor())
plt.close(fig)
print(OUT/'method_protocol_pending.png')
