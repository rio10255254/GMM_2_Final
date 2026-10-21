function tests = test_cd_error_reduction_figures
tests = functiontests(localfunctions);
end

function test_metrics_and_outputs(testCase)
out = make_center9_cd_error_reduction_figures(false);
verifyEqual(testCase, numel(out.metrics), 2);
verifyEqual(testCase, [out.metrics.pillars_improved], [7, 6]);
verifyGreaterThan(testCase, [out.metrics.mae_reduction_nm], [17, 9]);
verifyGreaterThan(testCase, [out.metrics.max_error_reduction_nm], [4, 28]);
for k = 1:numel(out.metrics)
    verifyGreaterThan(testCase, out.metrics(k).mae_reduction_percent, 20);
end

for k = 1:numel(out.figure_paths)
    verifyEqual(testCase, exist(out.figure_paths(k), 'file'), 2);
    info = imfinfo(out.figure_paths(k));
    verifyGreaterThan(testCase, info.Width, 1200);
    verifyGreaterThan(testCase, info.Height, 1000);
end
end
