"""Actual container checks preserve readable originals and historical failures."""
import gzip
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_model_archive_batch import inspect_data_format


def test_original_zip_members_are_all_crc_checked(tmp_path):
    path=tmp_path/'original.zip'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('inputs/camera.txt','original payload')
        archive.writestr('reports/failure.txt','original adverse record')
    result=inspect_data_format(path,'delivery.zip')
    assert result=={'format_status':'ORIGINAL_ZIP_ALL_MEMBERS_CRC_READABLE','members':2}


def test_broken_historical_zip_is_recorded_and_never_rewritten(tmp_path):
    path=tmp_path/'broken.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('source.txt',b'original payload')
    changed=bytearray(path.read_bytes());changed[changed.index(b'original payload')]^=1
    path.write_bytes(changed)
    result=inspect_data_format(path,'delivery.zip')
    assert 'FAILURE' in result['format_status']
    assert path.read_bytes()==changed


def test_original_gzip_is_read_through_the_crc_trailer(tmp_path):
    path=tmp_path/'complete.csv.gz'
    with gzip.open(path,'wb') as stream:stream.write(b'1,2,3\n'*1000)
    assert inspect_data_format(path,path.name)=={
        'format_status':'GZIP_STREAM_CRC_READABLE','uncompressed_bytes':6000}
