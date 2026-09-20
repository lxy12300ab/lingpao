import os
import sqlite3
import threading
from datetime import datetime, timedelta
from urllib.parse import quote, urlsplit
import httpx
from . import config, db

_lock = threading.Lock()

def list_backups():
    return [{'filename': p.name, 'bytes': p.stat().st_size,
             'created_at': datetime.fromtimestamp(p.stat().st_mtime, config.TZ).isoformat()}
            for p in sorted((config.DATA/'backups').glob('leap-*.db'), reverse=True)]

def create_backup():
    with _lock:
        stamp = datetime.now(config.TZ).strftime('%Y%m%d-%H%M%S-%f')
        path = config.DATA/'backups'/f'leap-{stamp}.db'
        temp = path.with_suffix('.partial')
        try:
            with db.connect() as source:
                dest = sqlite3.connect(temp)
                try:
                    source.backup(dest)
                    if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('备份完整性校验失败')
                finally:
                    dest.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        remote = 'disabled'
        url = os.getenv('WEBDAV_URL', '').strip()
        if url:
            try:
                if urlsplit(url).scheme != 'https':
                    raise ValueError('WebDAV 必须使用 HTTPS')
                with path.open('rb') as stream, httpx.Client(timeout=120, follow_redirects=False) as client:
                    response = client.put(url.rstrip('/')+'/'+quote(path.name), content=stream,
                        auth=(os.getenv('WEBDAV_USERNAME',''), os.getenv('WEBDAV_PASSWORD','')),
                        headers={'Content-Type':'application/octet-stream'})
                    response.raise_for_status()
                remote = 'ok'
            except Exception:
                # Do not put URL credentials, response bodies or secrets in logs.
                remote = 'failed'
        cutoff = datetime.now(config.TZ)-timedelta(days=config.RETENTION_DAYS)
        for old in (config.DATA/'backups').glob('leap-*.db'):
            if old != path and old.stat().st_mtime < cutoff.timestamp():
                old.unlink()
        with db.connect() as c:
            db.log(c, 'backup', path.name, 'warning' if remote=='failed' else 'ok', f'webdav={remote}')
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('last_backup', config.now()))
        return {'filename': path.name, 'bytes': path.stat().st_size, 'webdav': remote}
