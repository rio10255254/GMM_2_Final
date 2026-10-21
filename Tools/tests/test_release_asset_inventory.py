"""Final inventory checks include later pages and reject changed attachments."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import verify_project_release_assets as inventory


def asset(number):
    return {'id':number,'name':f'part{number}.zip','size':number,
            'digest':'sha256:'+str(number).zfill(64),'state':'uploaded'}


def test_complete_later_pages_are_not_replaced_with_embedded_assets(monkeypatch):
    all_assets=[asset(i) for i in range(1,121)]
    def request(*args):
        if args[0]=='release':return {'databaseId':5}
        if '--paginate' in args:
            assert '--slurp' in args and args[-1].endswith('/assets?per_page=100')
            return [all_assets[:100],all_assets[100:]]
        return {'id':5,'tag_name':'scope','draft':True,'assets':all_assets[:30]}
    monkeypatch.setattr(inventory,'gh_json',request)
    value=inventory.release_snapshot('owner/repo','scope',True)
    assert value['server_pages']==2 and len(value['assets'])==120
    last=all_assets[-1]
    assert inventory.check_assets([{'name':last['name'],'bytes':last['size'],'sha256':last['digest'][7:]}],value)[0]['asset_id']==120


def test_changed_or_incomplete_server_object_is_rejected():
    row=asset(1);spec={'name':row['name'],'bytes':row['size'],'sha256':row['digest'][7:]}
    for changed in [{**row,'size':2},{**row,'state':'starter'},{**row,'digest':None}]:
        with pytest.raises(ValueError,match='stored attachment differs'):
            inventory.check_assets([spec],{'assets':[changed]})


def test_unpublished_component_cannot_pass_final_inventory(monkeypatch):
    monkeypatch.setattr(inventory,'gh_json',lambda *args:{'databaseId':5} if args[0]=='release' else {'id':5,'tag_name':'scope','draft':True})
    with pytest.raises(ValueError,match='unpublished draft'):
        inventory.release_snapshot('owner/repo','scope')
