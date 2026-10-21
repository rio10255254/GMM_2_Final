"""Avoid hitting the server asset limit after a large image archive is uploaded."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_research_data_archive import assign_release_shards, predicted_parts


def test_thousands_of_parts_keep_every_batch_below_the_release_limit():
    batches = [{'batch': f'B{i:03}', 'predicted_parts': 9} for i in range(201)]
    releases = assign_release_shards(batches, 'research-images')
    assert len(releases) == 3
    assert len(batches) == 201
    assert all(row['planned_batch_assets'] <= 900 for row in releases)
    assert batches[0]['tag'] == 'research-images'
    assert batches[75]['tag'] == 'research-images-02'
    assert batches[150]['tag'] == 'research-images-03'


def test_packing_prediction_accounts_for_each_original_object_header():
    # The exact byte limit would fit without the per-object allowance. The
    # actual packer must start a second part, and routing must predict that.
    rows = [{'sha256': 'a' * 64, 'bytes': 900_000_000},
            {'sha256': 'b' * 64, 'bytes': 900_000_000}]
    assert predicted_parts(rows) == 2
    assert predicted_parts([]) == 0
