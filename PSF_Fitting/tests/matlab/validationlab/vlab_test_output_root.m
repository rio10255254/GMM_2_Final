function output_root = vlab_test_output_root(lab_root)
override_root = getenv('VLAB_TEST_OUTPUT_ROOT');
if isempty(override_root)
    output_root = fullfile(lab_root, 'outputs');
else
    output_root = override_root;
end
end
