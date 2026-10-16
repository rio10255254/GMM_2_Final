"""Numerical sensitivity follow-up; preserve initial small-step FP32 results."""
from fixed_example import fixture,tensors
from common import *

def main():
    setup();arrays,meta,_=fixture();source,a=tensors(arrays);results=[]
    for obs in [False,True]:
        m=new_model(obs,1265001,meta['profile']);m.eval();p=m.prior.head.weight
        d=m.forward_details(source);loss,_=objective(m,d,source,a,meta,CFG['loss_weights'],False)
        grad=torch.autograd.grad(loss,p)[0];direction=grad/grad.norm();analytic=float((grad*direction).sum());base=p.detach().clone();rows=[]
        with torch.no_grad():
            for eps in [.01,.003,.001,.0003,.0001]:
                vals=[]
                for sign in [1,-1]:
                    p.copy_(base+sign*eps*direction);dd=m.forward_details(source);ll,_=objective(m,dd,source,a,meta,CFG['loss_weights'],False);vals.append(float(ll))
                numeric=(vals[0]-vals[1])/(2*eps)
                rows.append(dict(epsilon=eps,numeric=numeric,relative_error=abs(numeric-analytic)/abs(analytic)))
            p.copy_(base)
        result=dict(observation_steps=obs,analytical=analytic,epsilon_sweep=rows,finite_difference_agrees_within_one_percent=sum(r['relative_error']<.01 for r in rows)>=2)
        results.append(result);print(json.dumps(result),flush=True)
    save(ROOT/'results/derivative_precision.json',dict(results=results,passed=all(r['finite_difference_agrees_within_one_percent'] for r in results),initial_results_retained=True,interpretation='Require agreement at two or more finite-difference scales; all scales reported'))
if __name__=='__main__':main()
