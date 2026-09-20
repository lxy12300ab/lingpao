import json
import sqlite3
from contextlib import contextmanager
from . import config
from .models import Dataset

@contextmanager
def connect():
    conn = sqlite3.connect(config.DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=30000')
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init():
    config.prepare()
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS screenshots (
          id INTEGER PRIMARY KEY, filename TEXT NOT NULL, uploaded_at TEXT NOT NULL,
          ocr_status TEXT NOT NULL, ocr_result TEXT, error_message TEXT);
        CREATE TABLE IF NOT EXISTS daily_mileage (
          id INTEGER PRIMARY KEY, date TEXT UNIQUE NOT NULL, km REAL NOT NULL CHECK(km>=0),
          source TEXT, screenshot_id INTEGER REFERENCES screenshots(id),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS weekly_energy (
          id INTEGER PRIMARY KEY, period TEXT UNIQUE NOT NULL, value REAL NOT NULL CHECK(value>0),
          screenshot_id INTEGER REFERENCES screenshots(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS energy_breakdown (
          id INTEGER PRIMARY KEY, period TEXT UNIQUE NOT NULL, total_kwh REAL NOT NULL,
          drive_pct REAL NOT NULL, ac_pct REAL NOT NULL, other_pct REAL NOT NULL,
          screenshot_id INTEGER REFERENCES screenshots(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS upload_log (
          id INTEGER PRIMARY KEY, action TEXT, target TEXT, status TEXT, message TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        PRAGMA user_version=1;
        ''')

def log(c, action, target, status, message):
    c.execute('INSERT INTO upload_log(action,target,status,message,created_at) VALUES(?,?,?,?,?)',
              (action, str(target), status, message, config.now()))

def merge(c, dataset: Dataset, screenshot_id=None, source='ocr'):
    # One transaction covers the whole batch, including audit and screenshot status.
    c.execute('BEGIN IMMEDIATE')
    result = {'inserted': 0, 'updated': 0, 'unchanged': 0, 'rejected': []}
    stamp = config.now()
    for row in dataset.daily:
        key = row.date.isoformat()
        old = c.execute('SELECT km FROM daily_mileage WHERE date=?', (key,)).fetchone()
        if old is None:
            c.execute('INSERT INTO daily_mileage(date,km,source,screenshot_id,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                      (key, row.km, source, screenshot_id, stamp, stamp))
            result['inserted'] += 1
        elif row.km > old['km']:
            c.execute('UPDATE daily_mileage SET km=?,source=?,screenshot_id=?,updated_at=? WHERE date=?',
                      (row.km, source, screenshot_id, stamp, key))
            result['updated'] += 1
        else:
            result['unchanged'] += 1
    for row in dataset.weekly:
        old = c.execute('SELECT value FROM weekly_energy WHERE period=?', (row.period,)).fetchone()
        if old is None:
            c.execute('INSERT INTO weekly_energy(period,value,screenshot_id,created_at,updated_at) VALUES(?,?,?,?,?)',
                      (row.period, row.value, screenshot_id, stamp, stamp))
            result['inserted'] += 1
        elif abs(row.value-old['value']) > old['value'] * 0.2 + 1e-9:
            result['rejected'].append({'period': row.period, 'old': old['value'], 'new': row.value,
                                       'reason': '偏差超过20%，保留历史值'})
        elif row.value > old['value']:
            c.execute('UPDATE weekly_energy SET value=?,screenshot_id=?,updated_at=? WHERE period=?',
                      (row.value, screenshot_id, stamp, row.period))
            result['updated'] += 1
        else:
            result['unchanged'] += 1
    for row in dataset.energy:
        cur = c.execute('INSERT OR IGNORE INTO energy_breakdown(period,total_kwh,drive_pct,ac_pct,other_pct,screenshot_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                        (row.period, row.totalKwh, row.drive, row.ac, row.other, screenshot_id, stamp, stamp))
        result['inserted' if cur.rowcount else 'unchanged'] += 1
    log(c, 'merge', screenshot_id or source, 'warning' if result['rejected'] else 'ok', json.dumps(result, ensure_ascii=False))
    return result

def get_data():
    with connect() as c:
        return {
            'daily': [dict(r) for r in c.execute('SELECT date,km FROM daily_mileage ORDER BY date')],
            'weekly': [dict(r) for r in c.execute('SELECT period,value FROM weekly_energy ORDER BY period')],
            'energy': [dict(r) for r in c.execute('SELECT period,total_kwh AS totalKwh,drive_pct AS drive,ac_pct AS ac,other_pct AS other FROM energy_breakdown ORDER BY period')],
        }
