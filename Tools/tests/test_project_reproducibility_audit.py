import sys
from pathlib import Path
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_reproducibility_audit import classify,coverage,safe_relative,owner,bounded_archive_source,dependency_directory

class AuditTests(unittest.TestCase):
    def test_historical_checkpoint_double_extension_is_not_missed(self):
        self.assertEqual(classify('Experiments/R94/weights/epoch_008.pth.tar'),'model')
    def test_tensor_training_bank_is_not_counted_as_a_trained_model(self):
        self.assertEqual(classify('Experiments/R130/data/training_pairs.pt'),'input_numeric')
    def test_same_size_is_never_marked_verified(self):
        self.assertEqual(coverage(12,None,12,'a'),'size_candidate_NOT_VERIFIED')
        self.assertEqual(coverage(12,'b',12,'a'),'content_changed')
        self.assertEqual(coverage(12,'a',12,'a'),'SHA256_VERIFIED')
    def test_metadata_path_cannot_escape_project(self):
        for value in ['../secret','C:/Users/private','/absolute/file']:
            with self.assertRaises(ValueError):safe_relative(value)
    def test_longest_experiment_scope_wins(self):
        scopes=[('experiments/r98/results/a','nested'),('experiments/r98','parent')]
        self.assertEqual(owner('Experiments/R98/results/a/table.csv',scopes),'nested')
    def test_credentials_are_explicitly_excluded(self):
        self.assertEqual(classify('Tools/private/credentials.json'),'private_excluded')
    def test_archive_projection_cannot_include_live_runs_or_own_downloads(self):
        archive=Path('/archive')
        for path in ['/archive','/archive/experiments','/archive/reproducibility/current','/archive/active_runs/live']:
            self.assertIsNone(bounded_archive_source(Path(path),archive))
        self.assertIsNotNone(bounded_archive_source(Path('/archive/experiments/R93'),archive))
    def test_historical_copied_inference_is_never_discarded_as_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'runtime';root.mkdir()
            (root/'infer.py').write_text('historical inference',encoding='utf-8')
            self.assertFalse(dependency_directory(root,'runtime'))
            (root/'python.exe').write_bytes(b'environment marker')
            self.assertTrue(dependency_directory(root,'runtime'))

if __name__=='__main__':unittest.main()
