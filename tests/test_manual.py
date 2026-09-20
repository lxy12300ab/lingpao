import json
from fastapi.testclient import TestClient
from app import config, db
from app.main import app
from app.models import Dataset

def test_manual_mileage_validation_audit_and_protection(storage):
    with TestClient(app) as client:
        url = '/api/daily/2026-09-01'
        body = {'km': 73, 'expected_km': None}
        assert client.put(url, json=body).status_code == 401
        client.headers['X-API-Key'] = config.TOKEN
        assert client.put(url, json=body, headers={'Origin': 'https://evil.test'}).status_code == 403
        assert client.put(url, json=body).status_code == 200
        assert client.put(url, json={'km': 30.5, 'expected_km': 73}).status_code == 200
        assert client.put(url, json={'km': 99, 'expected_km': 73}).status_code == 409
        for value in [-1, 3001, 'NaN', None]:
            assert client.put(url, json={'km': value, 'expected_km': 30.5}).status_code == 422
        assert client.put('/api/daily/2999-01-01', json=body).status_code == 422
        assert client.put('/api/daily/not-a-date', json=body).status_code == 422
        with db.connect() as c:
            result = db.merge(c, Dataset(daily=[{'date': '2026-09-01', 'km': 100}]))
        assert result['rejected']
        assert db.get_data()['daily'][0]['km'] == 30.5
        assert client.put(url, json={'km': 0, 'expected_km': 30.5}).status_code == 200
        with db.connect() as c:
            logs = list(c.execute("SELECT message FROM upload_log WHERE action='manual_daily' ORDER BY id"))
            assert len(logs) == 3
            assert json.loads(logs[-1]['message'])['before']['km'] == 30.5
            assert c.execute('SELECT source FROM daily_mileage').fetchone()['source'] == 'manual'
