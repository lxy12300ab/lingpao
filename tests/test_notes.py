import sqlite3
from fastapi.testclient import TestClient
from app import config, db, backup
from app.main import app
from app.models import Dataset


def test_daily_notes_atomic_and_independent(storage):
    with TestClient(app) as client:
        url = '/api/daily/2026-09-19'
        assert client.get('/api/notes').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + config.TOKEN
        body = {'km': None, 'expected_km': None, 'note': '接孩子\n顺路买菜', 'expected_note': ''}
        assert client.put(url, json=body).status_code == 200
        assert db.get_data()['daily'] == []
        assert client.get('/api/notes').json()[0]['note'] == body['note']
        with db.connect() as c:
            db.merge(c, Dataset(daily=[{'date': '2026-09-19', 'km': 73}]))
        body.update(km=73, expected_km=73, expected_note=body['note'], note='周末出行')
        assert client.put(url, json=body).status_code == 200
        with db.connect() as c:
            assert c.execute('SELECT source FROM daily_mileage').fetchone()[0] == 'ocr'
            db.merge(c, Dataset(daily=[{'date': '2026-09-19', 'km': 80}]))
        assert client.get('/api/notes').json()[0]['note'] == '周末出行'
        # A stale note cannot partially change the mileage.
        body.update(km=90, expected_km=80)
        assert client.put(url, json=body).status_code == 409
        assert db.get_data()['daily'][0]['km'] == 80
        result = backup.create_backup()
        with sqlite3.connect(config.DATA/'backups'/result['filename']) as c:
            assert c.execute('SELECT note FROM daily_notes').fetchone()[0] == '周末出行'
        body.update(km=80, expected_note='周末出行', note='')
        assert client.put(url, json=body).status_code == 200
        assert client.get('/api/notes').json() == []
        body.update(expected_note='', note='x'*2001)
        assert client.put(url, json=body).status_code == 422
        assert client.put('/api/daily/2999-01-01', json=body).status_code == 422
        db.init()
        assert db.get_data()['daily'][0]['km'] == 80
