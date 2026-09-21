import json
from fastapi.testclient import TestClient
from app import config, db
from app.main import app


def test_dismiss_restore_preserves_data(storage):
    with TestClient(app) as client:
        with db.connect() as c:
            sid = c.execute(
                'INSERT INTO screenshots(filename,uploaded_at,ocr_status,ocr_result) VALUES(?,?,?,?)',
                ('kept.png', config.now(), 'review', json.dumps({'data': {'daily': []}})),
            ).lastrowid
        url = f'/api/screenshots/{sid}'
        assert client.post(url + '/dismiss').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + config.TOKEN
        before = db.get_data()
        assert client.post(url + '/dismiss').json()['status'] == 'dismissed'
        assert client.post(url + '/dismiss').status_code == 200
        assert client.get('/api/screenshots').json()[0]['ocr_status'] == 'dismissed'
        proposal = {'daily': [{'date': '2026-09-19', 'km': 73}]}
        assert client.post(url + '/confirm', json=proposal).status_code == 409
        assert db.get_data() == before
        assert client.post(url + '/restore').json()['status'] == 'review'
        assert client.post(url + '/confirm', json=proposal).status_code == 200
        assert client.post(url + '/dismiss').status_code == 409
        assert db.get_data()['daily'][0]['km'] == 73
        assert client.post('/api/screenshots/999999/dismiss').status_code == 404
        with db.connect() as c:
            row = c.execute('SELECT filename FROM screenshots WHERE id=?', (sid,)).fetchone()
            assert row['filename'] == 'kept.png'
            assert c.execute("SELECT count(*) FROM upload_log WHERE action='screenshot_status'").fetchone()[0] == 2
