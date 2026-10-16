function t=test_psf_figures
t=functiontests(localfunctions);
end
function test_metrics(tc)
r=make_center9_psf_analysis_figures(false,false);
m=r.metrics;
verifyEqual(tc,string(m.magnification),["20x";"50x"]);
verifyGreaterThan(tc,m.fwhm_x_um,ones(2,1));
verifyLessThan(tc,m.fwhm_x_um,1.5*ones(2,1));
verifyGreaterThan(tc,m.r80_um,m.r50_um);
verifyGreaterThan(tc,m.mtf10_mean_cyc_per_um,m.mtf50_mean_cyc_per_um);
verifyLessThan(tc,m.second_moment_axis_ratio,1.05*ones(2,1));
verifyGreaterThan(tc,m.fit_correlation,0.7*ones(2,1));
verifyLessThan(tc,m.fit_nrmse,0.6*ones(2,1));
end
