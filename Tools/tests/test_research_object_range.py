"""Check actual ZIP64 partial recovery and protection of existing user files."""
import hashlib
import io
from pathlib import Path
import random
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from download_research_object_range import RangeReader, restore_member


def sample_archive():
    wanted = b'original fixed research graph' * 1000
    sha = hashlib.sha256(wanted).hexdigest()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('objects/unrelated-large-object', random.Random(17).randbytes(3 * 1024**2))
        with archive.open('objects/' + sha, 'w', force_zip64=True) as stream:
            stream.write(wanted)
    return output.getvalue(), wanted, sha


def test_only_target_zip64_member_is_received_and_exactly_written(tmp_path):
    data, wanted, sha = sample_archive()
    reader = RangeReader(len(data), lambda start, end: data[start:end+1])
    result = restore_member(reader, sha, len(wanted), tmp_path / 'model.onnx')
    assert (tmp_path / 'model.onnx').read_bytes() == wanted
    assert result['sha256'] == sha and reader.requested_bytes < len(data) // 10
    assert result['entire_archive_part_downloaded'] is False


def test_user_file_is_preserved_before_any_range_request(tmp_path):
    target = tmp_path / 'user.onnx'
    target.write_bytes(b'user changed data')
    def forbidden(*args):
        raise AssertionError('No network read should occur')
    with pytest.raises(FileExistsError):
        restore_member(RangeReader(100, forbidden), 'a' * 64, 10, target)
    assert target.read_bytes() == b'user changed data'


def test_wrong_original_identity_never_receives_a_final_name(tmp_path):
    data, wanted, sha = sample_archive()
    reader = RangeReader(len(data), lambda start, end: data[start:end+1])
    with pytest.raises(ValueError, match='absent, ambiguous or differs'):
        restore_member(reader, sha, len(wanted) + 1, tmp_path / 'wrong.onnx')
    assert not (tmp_path / 'wrong.onnx').exists()


def test_valid_zip_crc_cannot_hide_changed_original_file_bytes(tmp_path):
    original = b'original weights'
    sha = hashlib.sha256(original).hexdigest()
    target = tmp_path / 'corrupt.onnx'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('objects/' + sha, b'changed weights!')
    data = stream.getvalue()
    with pytest.raises(ValueError, match='frozen identity'):
        restore_member(RangeReader(len(data), lambda a, b: data[a:b+1]), sha, len(original), target)
    assert not target.exists()


def test_user_file_created_during_download_is_never_overwritten(tmp_path):
    data, wanted, sha = sample_archive()
    target = tmp_path / 'concurrent.onnx'
    def fetch(start, end):
        if not target.exists():
            target.write_bytes(b'user file created while downloading')
        return data[start:end+1]
    with pytest.raises(FileExistsError):
        restore_member(RangeReader(len(data), fetch), sha, len(wanted), target)
    assert target.read_bytes() == b'user file created while downloading'
