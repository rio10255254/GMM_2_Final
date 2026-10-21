from pathlib import Path
import sys,argparse,types,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import train_core as trainer
def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['A','C']);p.add_argument('--seed',type=int);p.add_argument('--matrix',action='store_true');a=p.parse_args()
    if a.matrix:
        from rt import load,save,record
        assert load(ROOT/'results/preflight.json')['passed'];cfg=load(ROOT/'config/study.json');rows=[]
        for seed in cfg['seeds']:
            for arm in cfg['arms']:
                subprocess.run([sys.executable,'-B',__file__,'--arm',arm,'--seed',str(seed)],check=True);rows.append(dict(arm=arm,seed=seed,complete=record(ROOT/f'runs/R134_{arm}_s{seed}/complete.json')))
        save(ROOT/'results/matrix_complete.json',dict(runs=rows,updates=2048,B_D_not_executed=True));return
    CFG=types.SimpleNamespace(MODEL_NAME=f'R134_{a.arm}_s{a.seed}')
    trainer.MODEL_NAME_BASE=CFG.MODEL_NAME
    trainer.run(a.arm,a.seed)
if __name__=='__main__':main()
