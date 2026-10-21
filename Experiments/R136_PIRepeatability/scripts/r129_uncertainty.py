"""GUM-oriented Type A assessment; missing Type B inputs are never set to zero."""
from common import *
import numpy as np,pandas as pd
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_nw_panel
from scipy import stats
OUT=ROOT/'results/r129_uncertainty';T=ROOT/'results/lsc/analysis/tables'

def hac_cov(X,res,groups,lag):
    n,p=X.shape;score=X*res[:,None];meat=score.T@score
    for h in range(1,lag+1):
        valid=groups[h:]==groups[:-h];cross=score[h:][valid].T@score[:-h][valid];meat+=(1-h/(lag+1))*(cross+cross.T)
    bread=np.linalg.inv(X.T@X);return bread@meat@bread*n/(n-p)

def main():
    OUT.mkdir(parents=True,exist_ok=True);source=T/'all_measurements.csv';d=pd.read_csv(source);d=d[(d.model=='R129')&(d.view=='nominal_all30')&(d.reader=='LSC')&(d.roi=='center9')&(d.precision=='full')].copy();assert len(d)==1800 and set(d.status)=={'ok'}
    existing=pd.read_csv(T/'per_position.csv');existing=existing[(existing.model=='R129')&(existing.view=='nominal_all30')]
    rules=dict(measurand='PI-referenced indication error of the9-circle median LSC displacement at a fixed position/step',reference_unit='nm',input=record(source),n_per_position=30,positions=60,single_component='sample SD of unmodified errors across the complete observed capture session;not a future prediction guarantee',mean_model='error = intercept + centered elapsed minutes + centered early6/late24 indicator;intercept is expected average error for the observed time design',mean_covariance='Newey-West Bartlett HAC,lag3 in acquisition order,finite correction30/27;no lag products across11minute acquisition break',lags_sensitivity=[2,3,5],coverage='k=2 component display only;no guaranteed95%total coverage asserted',assumptions=['Mean model linear in elapsed time plus protocol-block offset','Within-block residual dependence adequately approximated by3lag HAC;small-sample model uncertainty is not fully identified','11minute gap separates stochastic residual blocks;shared calibration uncertainty remains unquantified','Scale0.1725um/px and existing direction transform conditioned on;their calibration uncertainty not zero and not included'],system_total_u=None,system_total_U=None,unknown_components=['PI displacement calibration and its cross-position covariance','effective optical scale/direction calibration and dependence on PI','uncharacterized timing and between-session conditions'],bias_correction_applied=False)
    save(OUT/'method.json',rules);rows=[];checks=[]
    for (kind,j),g in d.groupby(['kind','j']):
        g=g.sort_values('run_index');assert g.run_index.tolist()==list(range(1,31));e=g.error_nm.to_numpy();n=len(e);times=pd.to_datetime(g.recorded_at,utc=True);minutes=(times-times.iloc[0]).dt.total_seconds().to_numpy()/60;group=(g.run_index.to_numpy()>6).astype(int)
        X=np.column_stack([np.ones(n),minutes-minutes.mean(),group-group.mean()]);fit=sm.OLS(e,X).fit();res=fit.resid;assert abs(fit.params[0]-e.mean())<1e-10
        estimates={}
        for lag in [2,3,5]:
            cov=hac_cov(X,res,group,lag);ref=cov_nw_panel(fit,nlags=lag,groupidx=[(0,6),(6,30)],use_correction='hac');delta=float(np.abs(cov-ref).max());assert delta<1e-8;estimates[lag]=float(np.sqrt(max(cov[0,0],0)));checks.append(delta)
        s=float(e.std(ddof=1));u=estimates[3];prior=existing[(existing.kind==kind)&(existing.position_index==j)].iloc[0];assert abs(s-prior.repeatability_sd_nm)<1e-7
        iid=s/np.sqrt(n);ci95_iid=stats.t.ppf(.975,n-1)*iid
        # Algebraic unit check: intercept-only HC1 must recover s^2/n.
        iid_cov=hac_cov(np.ones((n,1)),e-e.mean(),np.zeros(n),0);assert abs(iid_cov[0,0]-s*s/n)<1e-10
        rows.append(dict(kind=kind,position_index=int(j),n=n,mean_PI_um=float(g.pi_dy_um.mean()),mean_LSC_um=float(g.image_along_um.mean()),bias_nm=float(e.mean()),single_session_repeatability_s_nm=s,repeatability_2s_nm=2*s,mean_uA_time_model_nm=u,mean_UA_k2_time_model_nm=2*u,mean_bias_k2_lower_nm=float(e.mean()-2*u),mean_bias_k2_upper_nm=float(e.mean()+2*u),iid_mean_uA_reference_only_nm=float(iid),iid_t29_halfwidth_reference_only_nm=float(ci95_iid),mean_uA_lag2_nm=estimates[2],mean_uA_lag5_nm=estimates[5],mean_uA_sensitivity_min_nm=min(estimates.values()),mean_uA_sensitivity_max_nm=max(estimates.values()),drift_nm_per_min=float(fit.params[1]),late_block_offset_nm=float(fit.params[2]),residual_sd_nm=float(np.sqrt(sum(res**2)/(n-3))),raw_error_lag1_correlation=float(np.corrcoef(e[:-1],e[1:])[0,1]),residual_lag1_correlation=float(np.corrcoef(res[:-1],res[1:])[0,1]),observed_error_min_nm=float(e.min()),observed_error_max_nm=float(e.max()),mean_first6_nm=float(e[:6].mean()),mean_late24_nm=float(e[6:].mean())))
    result=pd.DataFrame(rows);result.to_csv(OUT/'r129_uncertainty_by_position.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    overview=[]
    for kind,g in result.groupby('kind'):
        worst=g.loc[g.single_session_repeatability_s_nm.idxmax()]
        overview.append(dict(kind=kind,positions=30,s_mean_descriptive_nm=float(g.single_session_repeatability_s_nm.mean()),s_rms_descriptive_nm=float(np.sqrt(np.mean(g.single_session_repeatability_s_nm**2))),s_min_nm=float(g.single_session_repeatability_s_nm.min()),s_max_nm=float(worst.single_session_repeatability_s_nm),max_s_position=int(worst.position_index),max_2s_nm=float(worst.repeatability_2s_nm),largest_abs_bias_nm=float(g.bias_nm.abs().max())))
    save(OUT/'summary.json',dict(scope='Within-session PI-referenced Type A components only,not fullsystem uncertainty',overview=overview,selected=result[((result.kind=='adjacent')&(result.position_index==1))|((result.kind=='start')&(result.position_index.isin([10,20,30])))].to_dict('records'),system_combined_standard_uncertainty=None,system_expanded_uncertainty=None,reason='Required Type B calibration/covariance information missing',verified_covariance_against_statsmodels_max=float(max(checks)),completed_utc=now()))
    budget=[dict(component='Observed repeated indication-error spread',available=True,source='r129_uncertainty_by_position.csv',handling='Reported as session-specific s;includes reference random fluctuations and observedtimevariation'),dict(component='Uncertainty of average indication error',available=True,source='time/protocol mean model with HACcovariance',handling='Model conditional TypeA;not sqrt30blindly;lag sensitivity retained'),dict(component='PI displacement calibration',available=False,source='Not supplied',handling='Unknown,not zero;do not re-add PI random noise already represented'),dict(component='Scale/direction calibration',available=False,source='nominal pitch and priorPI-basedfit are not calibration uncertainty',handling='Unknown,not zero;sharedPI dependence must be propagated jointly'),dict(component='Timing/environment outside observed session',available=False,source='Not independently characterized',handling='No universal or between-day scope'),dict(component='Bias correction',available=False,source='Currentmeanbias known;no independently validated correction applied',handling='Keep bias separate;do not add its square and label RMSEasuncertainty')]
    save(OUT/'uncertainty_budget.json',dict(components=budget,full_combined_u=None,full_expanded_U=None))
    result.to_csv(OUT/'readable_results.csv',columns=['kind','position_index','mean_PI_um','bias_nm','single_session_repeatability_s_nm','repeatability_2s_nm','mean_uA_time_model_nm','mean_UA_k2_time_model_nm'],index=False,encoding='utf-8-sig',float_format='%.6f')
    print(result[((result.kind=='adjacent')&(result.position_index==1))|((result.kind=='start')&(result.position_index.isin([10,20,30])))][['kind','position_index','bias_nm','single_session_repeatability_s_nm','mean_uA_time_model_nm','mean_UA_k2_time_model_nm','mean_uA_lag2_nm','mean_uA_lag5_nm']].to_string(index=False));print(overview,flush=True)
if __name__=='__main__':main()
