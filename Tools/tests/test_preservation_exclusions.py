"""Private backups stay excluded even if copied under a different archive name."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_preservation_exclusions import excluded


POLICY={'excluded_path_prefixes':['_codex_store_backups'],
        'excluded_content_objects':[{'sha256':'a'*64,'bytes':123}]}


def test_private_backup_prefix_is_excluded_without_hiding_a_research_package():
    assert excluded({'path':'_codex_store_backups/old/runtime.zip'},POLICY)
    assert not excluded({'path':'Deliverables/R61_original.zip','sha256':'b'*64,'bytes':123},POLICY)


def test_same_private_archive_bytes_cannot_reenter_through_an_alias():
    assert excluded({'logical_path':'Historical_Archive/copy.zip','sha256':'a'*64,'bytes':123},POLICY)
    assert not excluded({'path':'data/observation.npy','sha256':'a'*64,'bytes':124},POLICY)
