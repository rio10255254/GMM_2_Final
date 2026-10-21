classdef test_center_9pillar_tools < matlab.unittest.TestCase
    methods (Test)
        function semRadiusIsConvertedToDiameter(testCase)
            expected_radius_nm = [
                1310.1071872032830, 1310.0081858573494, 1321.1577900710545
                1310.2142785890380, 1304.3597689145038, 1329.3068965988240
                1310.8899993469824, 1299.3758269507834, 1338.3982848246214];
            radius_nm = center_9pillar_sem_radius_nm();
            cd_nm = center_9pillar_sem_cd();

            testCase.verifyEqual(radius_nm, expected_radius_nm, 'AbsTol', 1e-9);
            testCase.verifyEqual(cd_nm, 2 * expected_radius_nm, 'AbsTol', 1e-9);
            testCase.verifyEqual(mean(cd_nm, 'all'), 2629.7373818569868, 'AbsTol', 1e-9);
        end

        function diameterPixelConversionUsesObjectPlaneSampling(testCase)
            cd_nm = center_9pillar_sem_cd();
            px20 = center_9pillar_cd_pixels(cd_nm, 20, 3.45);
            px50 = center_9pillar_cd_pixels(cd_nm, 50, 3.45);

            testCase.verifyEqual(px20, cd_nm / 172.5, 'AbsTol', 1e-12);
            testCase.verifyEqual(px50, cd_nm / 69.0, 'AbsTol', 1e-12);
            testCase.verifyGreaterThan(min(px20, [], 'all'), 15);
            testCase.verifyGreaterThan(min(px50, [], 'all'), 37);
        end

        function orientationKeepsPhysicalValuesWithoutRelabeling(testCase)
            cd_nm = center_9pillar_sem_cd();
            testCase.verifyEqual(orient_center_9pillar_cd(cd_nm, "bottom-left"), cd_nm);
            testCase.verifyEqual(orient_center_9pillar_cd(cd_nm, "top-left"), rot90(cd_nm, -1));
        end
    end
end
