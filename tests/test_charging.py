from fastapi.testclient import TestClient
from app.main import app
from app import config, db

def test_charge_lifecycle(storage):
    with TestClient(app) as c:
        assert c.get('/api/charging').status_code == 401
        c.headers['X-API-Key']=config.TOKEN
        body=dict(date='2024-10-18',start_pct=20,end_pct=100,location='home')
        r=c.post('/api/charging',json=body)
        assert r.status_code==200
        first=r.json()
        assert first['estimated_kwh']==65.52 and first['loss_pct'] is None
        assert c.post('/api/charging',json=body).json()['id']!=first['id']
        path='/api/charging/'+str(first['id'])
        assert c.put(path,json={**body,'grid_kwh':72}).status_code==409
        r=c.put(path,json={**body,'grid_kwh':72,'expected_revision':first['revision']})
        assert r.json()['loss_pct']==9
        revision=r.json()['revision']
        for bad in [dict(start_pct=-1),dict(end_pct=19),dict(end_pct=101),dict(grid_kwh=0),dict(grid_kwh='NaN'),dict(date='2999-01-01')]:
            assert c.post('/api/charging',json={**body,**bad}).status_code==422
        assert c.request('DELETE',path,json={'expected_revision':first['revision']}).status_code==409
        assert c.request('DELETE',path,json={'expected_revision':revision}).status_code==200
        assert len(c.get('/api/charging').json()['records'])==1
        with db.connect() as conn:
            assert conn.execute('SELECT deleted FROM charging WHERE id=?',(first['id'],)).fetchone()[0]==1
        assert c.post('/api/charging/meter',json={'month':'2024-10','kwh':300}).status_code==200
        assert c.post('/api/charging/meter',json={'month':'2024-10','kwh':301}).status_code==409
        assert c.post('/api/charging/meter',json={'month':'2024-13','kwh':301}).status_code==422
        meter=c.get('/api/charging').json()['meters'][0]
        assert c.post('/api/charging/meter',json={'month':'2024-10','kwh':None,'expected_revision':meter['revision']}).status_code==200
        assert c.post('/api/charging',json=body,headers={'Origin':'https://evil.test'}).status_code==403
        from app.backup import create_backup
        import sqlite3
        backup=create_backup()
        with sqlite3.connect(storage/'backups'/backup['filename']) as saved:
            assert saved.execute('SELECT count(*) FROM charging').fetchone()[0]==2
            assert saved.execute('SELECT count(*) FROM charging_meter').fetchone()[0]==1
