import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import pytest
from pydantic import ValidationError
from app import db, backup, config
from app.models import Dataset

PERIOD='2026/09/07 - 2026/09/13'

def merge(**kwargs):
    with db.connect() as c:
        return db.merge(c,Dataset(**kwargs),source='test')

def test_daily_max_and_weekly_protection(storage):
    merge(daily=[{'date':'2026-09-19','km':73}],weekly=[{'period':PERIOD,'value':10}])
    merge(daily=[{'date':'2026-09-19','km':40}])
    merge(daily=[{'date':'2026-09-19','km':75}],weekly=[{'period':PERIOD,'value':12}])
    r=merge(weekly=[{'period':PERIOD,'value':20}])
    assert len(r['rejected'])==1
    r=merge(weekly=[{'period':PERIOD,'value':5}])
    assert len(r['rejected'])==1
    assert db.get_data()['daily']==[{'date':'2026-09-19','km':75}]
    assert db.get_data()['weekly'][0]['value']==12

def test_energy_append_only(storage):
    entry={'period':PERIOD,'totalKwh':68.1,'drive':85.61,'ac':6.02,'other':8.37}
    merge(energy=[entry])
    merge(energy=[{**entry,'totalKwh':70}])
    assert db.get_data()['energy'][0]['totalKwh']==68.1

def test_concurrent_max(storage):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n:merge(daily=[{'date':'2026-09-19','km':n}]),range(40,100)))
    assert db.get_data()['daily'][0]['km']==99

def test_backup_integrity_and_retention(storage):
    import os,time
    old=storage/'backups'/'leap-old.db';old.write_bytes(b'old')
    os.utime(old,(time.time()-91*86400,)*2)
    user_file=storage/'backups'/'keep.txt';user_file.write_text('keep')
    merge(daily=[{'date':'2026-09-19','km':73}])
    result=backup.create_backup()
    conn=sqlite3.connect(storage/'backups'/result['filename'])
    assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert conn.execute('SELECT km FROM daily_mileage').fetchone()[0]==73
    conn.close()
    assert not old.exists() and user_file.exists()

def test_hundred_days_under_one_mb(storage):
    merge(daily=[{'date':(date(2026,1,1)+timedelta(days=i)).isoformat(),'km':73} for i in range(100)])
    result=backup.create_backup()
    assert result['bytes']<1_000_000

@pytest.mark.parametrize('payload',[
    {'daily':[{'date':'2026-02-30','km':1}]},
    {'daily':[{'date':'2026-02-01','km':float('nan')}]},
    {'weekly':[{'period':'<script>alert(1)</script>','value':12}]},
    {'weekly':[{'period':'2026/01/01 - 2026/01/02','value':12}]},
    {'energy':[{'period':PERIOD,'totalKwh':68,'drive':90,'ac':20,'other':10}]},
    {'daily':[{'date':'2026-01-01','km':1},{'date':'2026-01-01','km':2}]},
])
def test_reject_invalid(payload):
    with pytest.raises(ValidationError):Dataset(**payload)

def test_transaction_rolls_back(storage):
    with pytest.raises(RuntimeError):
        with db.connect() as c:
            db.merge(c,Dataset(daily=[{'date':'2026-09-19','km':73}]))
            raise RuntimeError('simulate interrupted upload')
    assert not db.get_data()['daily']
