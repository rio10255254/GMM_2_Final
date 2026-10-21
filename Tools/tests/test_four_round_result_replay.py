"""Guard against false completion and erased rollback history in preservation."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replay_four_round_results import committed_rows, sem_summary

class ReplayTests(unittest.TestCase):
    def test_rollback_preserves_both_rows_but_commits_replayed_epoch(self):
        rows,removed,total=committed_rows([('initial',[{'epoch':'1','val':'7'},{'epoch':'2','val':'9'}]),
                                          ('continuation',[{'epoch':'2','val':'3'},{'epoch':'3','val':'1'}])],3)
        self.assertEqual(total,4)
        self.assertEqual(removed[0]['superseded']['values']['val'],'9')
        self.assertEqual(rows[1]['source'],'continuation')
        self.assertEqual(rows[1]['values']['val'],'3')
    def test_missing_epoch_rejected(self):
        with self.assertRaises(ValueError):committed_rows([('x',[{'epoch':'1'},{'epoch':'3'}])],3)
    def test_nonfinite_measurement_rejected(self):
        with self.assertRaises(ValueError):committed_rows([('x',[{'epoch':'1','value':'NaN'}])],1)
    def test_repeated_exposures_do_not_replace_missing_physical_pillars(self):
        # A large row count from one pillar cannot pass as 36 independent units.
        rows=[{'method':'Raw','pillar_id':'1','exposure':str(i),**{k:'0.5' for k in ['iou','dice','mean_boundary_distance_pitch_pct','hd95_pitch_pct','area_error_pct','perimeter_error_pct','circularity_abs_error']}} for i in range(12)]
        with self.assertRaises(ValueError):sem_summary(rows)

if __name__=='__main__':unittest.main()
