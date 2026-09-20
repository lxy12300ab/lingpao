"""Single-process scheduler. Startup catch-up replaces an extra cron daemon."""
import logging
import re
import threading
import uuid
from datetime import datetime, date
from . import config, db, backup, service

logger = logging.getLogger(__name__)

def scan_inbox():
    for path in sorted((config.DATA/'inbox').iterdir()):
        if not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):
            continue
        # Copy as .part then atomically rename; additionally skip recently modified files.
        if datetime.now().timestamp()-path.stat().st_mtime < 60:
            continue
        match = re.match(r'^(\d{4}-\d{2}-\d{2})[_ -]', path.name)
        if not match:
            path.replace(config.DATA/'failed'/f'{uuid.uuid4().hex}-{path.name}')
            with db.connect() as c:
                db.log(c, 'inbox', path.name, 'failed', '文件名必须以 YYYY-MM-DD_ 开头')
            continue
        dest = config.DATA/'screenshots'/f'{uuid.uuid4().hex}{path.suffix.lower()}'
        try:
            captured = date.fromisoformat(match[1])
            # Keep original until success so a busy OCR worker can retry next scan.
            import shutil
            shutil.copyfile(path, dest)
            result = service.process_file(dest, captured)
            path.replace(config.DATA/'processed'/f'{result["id"]}-{path.name}')
        except BlockingIOError:
            dest.unlink(missing_ok=True)
            break
        except Exception:
            path.replace(config.DATA/'failed'/f'{uuid.uuid4().hex}-{path.name}')
            logger.exception('Inbox processing failed')

def tick():
    now = datetime.now(config.TZ)
    hour = now.strftime('%Y-%m-%dT%H')
    with db.connect() as c:
        settings = dict(c.execute('SELECT key,value FROM settings').fetchall())
    if settings.get('last_inbox_hour') != hour:
        scan_inbox()
        with db.connect() as c:
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('last_inbox_hour',hour))
    if now.hour >= 3 and settings.get('last_backup','')[:10] != now.date().isoformat():
        backup.create_backup()
    # Remote failures are visible in logs; retry the next day or manually from the UI.

def run(stop: threading.Event):
    while not stop.is_set():
        try:
            tick()
        except Exception:
            logger.exception('Scheduled task failed; will retry')
        stop.wait(30)
