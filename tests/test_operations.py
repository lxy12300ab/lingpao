import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime
from app import config, db, backup, tasks, service
from app.models import Dataset

def test_remote_failure_keeps_local(storage,monkeypatch):
    monkeypatch.setenv('WEBDAV_URL','http://invalid.example/backup')
    result=backup.create_backup()
    assert result['webdav']=='failed'
    assert (storage/'backups'/result['filename']).exists()

def test_remote_success(storage,monkeypatch):
    monkeypatch.setenv('WEBDAV_URL','https://example.test/backup')
    class Response:
        def raise_for_status(self): pass
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def put(self,url,content,**kwargs):
            assert url.startswith('https://example.test/backup/leap-')
            assert content.read(16)==b'SQLite format 3\x00'
            return Response()
    monkeypatch.setattr(backup.httpx,'Client',Client)
    assert backup.create_backup()['webdav']=='ok'

def test_inbox_naming_and_busy_retry(storage,monkeypatch):
    good=storage/'inbox'/'2026-09-19_test.png';good.write_bytes(b'fixture')
    wrong=storage/'inbox'/'unknown.png';wrong.write_bytes(b'fixture')
    for file in (good,wrong):os.utime(file,(1,1))
    def busy(*args): raise BlockingIOError()
    monkeypatch.setattr(service,'process_file',busy)
    tasks.scan_inbox()
    assert good.exists()
    monkeypatch.setattr(service,'process_file',lambda *a:{'id':1,'status':'review'})
    tasks.scan_inbox()
    assert not good.exists() and not wrong.exists()
    assert len(list((storage/'processed').iterdir()))==1
    assert len(list((storage/'failed').iterdir()))==1

def test_scheduler_catchup_once(storage,monkeypatch):
    class Clock:
        @classmethod
        def now(cls,tz):return datetime(2026,9,19,4,5,tzinfo=tz)
    monkeypatch.setattr(tasks,'datetime',Clock)
    calls=[]
    monkeypatch.setattr(tasks,'scan_inbox',lambda:calls.append('scan'))
    def fake_backup():
        calls.append('backup')
        with db.connect() as c:c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('last_backup','2026-09-19T04:05:00+08:00'))
    monkeypatch.setattr(backup,'create_backup',fake_backup)
    tasks.tick();tasks.tick()
    assert calls==['scan','backup']

def test_migrate_and_restore_roundtrip(storage):
    root=Path(__file__).resolve().parents[1]
    env={**os.environ,'DATA_DIR':str(storage),'WEBDAV_URL':''}
    subprocess.run([sys.executable,str(root/'migrate.py'),str(root/'data.sample.json')],env=env,check=True,capture_output=True)
    expected=db.get_data()
    assert len(expected['daily'])==len(json.loads((root/'data.sample.json').read_text())['daily'])
    result=backup.create_backup()
    with db.connect() as c:db.merge(c,Dataset(daily=[{'date':'2026-09-19','km':99}]),source='test')
    subprocess.run([sys.executable,str(root/'restore.py'),str(storage/'backups'/result['filename']),'--confirm-app-stopped'],env=env,check=True,capture_output=True)
    assert db.get_data()==expected
    assert len(list((storage/'backups').glob('before-restore-*.db')))==1
