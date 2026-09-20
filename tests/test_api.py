import io
import json
from PIL import Image
from fastapi.testclient import TestClient
from app import config, db, ocr
from app.main import app

def test_auth_cache_health_export_and_backup(storage):
    with TestClient(app) as client:
        assert client.get('/api/health').json()['status']=='ok'
        assert client.get('/api/data').status_code==401
        assert client.post('/api/admin/backup').status_code==401
        client.headers['Authorization']='Bearer '+config.TOKEN
        assert client.get('/api/data').json()=={'daily':[],'weekly':[],'energy':[]}
        r=client.get('/')
        assert 'no-store' in r.headers['cache-control'] and '__BUILD__' not in r.text
        assert client.get('/api/version').json()['build']==config.BUILD
        result=client.post('/api/admin/backup').json()
        assert result['bytes']>0
        assert client.get('/api/admin/backups').json()[0]['filename']==result['filename']
        assert client.get('/api/admin/backups/'+result['filename']).status_code==200
        assert client.post('/api/admin/backup',headers={'Origin':'https://evil.test'}).status_code==403

def png():
    out=io.BytesIO();Image.new('RGB',(600,1200),'white').save(out,format='PNG');return out.getvalue()

def test_upload_review_then_confirm(storage,monkeypatch):
    proposal={'data':{'daily':[{'date':'2026-09-19','km':73}],'weekly':[],'energy':[]},'warnings':['待核对'],'evidence':{}}
    monkeypatch.setattr(ocr,'recognize',lambda *a:proposal)
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer '+config.TOKEN
        assert client.post('/api/upload',files={'file':('x.png',png())}).status_code==422
        r=client.post('/api/upload',files={'file':('../../x.png',png())},data={'captured_date':'2026-09-19'})
        assert r.status_code==200 and r.json()['status']=='review'
        assert not db.get_data()['daily']
        sid=r.json()['id']
        assert client.get(f'/api/screenshots/{sid}/image').status_code==200
        confirmed=client.post(f'/api/screenshots/{sid}/confirm',json=proposal['data'])
        assert confirmed.json()['inserted']==1
        assert client.post(f'/api/screenshots/{sid}/confirm',json=proposal['data']).json()['unchanged']==1
        assert not list(storage.glob('x.png'))
        assert client.post('/api/upload',files={'file':('x.png',b'not an image')},data={'captured_date':'2026-09-19'}).status_code==422

def test_clean_upload_merges(storage,monkeypatch):
    monkeypatch.setattr(ocr,'recognize',lambda *a:{'data':{'daily':[{'date':'2026-09-19','km':73}]},'warnings':[]})
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer '+config.TOKEN
        r=client.post('/api/upload',files={'file':('x.png',png())},data={'captured_date':'2026-09-19'})
        assert r.json()['status']=='done'
        assert db.get_data()['daily'][0]['km']==73
