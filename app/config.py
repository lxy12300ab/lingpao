import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv('DATA_DIR', str(ROOT.parent / 'data'))).resolve()
DB = DATA / 'leap.db'
BUILD = os.getenv('BUILD', '2026.09.25.1')
if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', BUILD):
    raise ValueError('BUILD 只能使用字母、数字、点、横线和下划线')
TOKEN = os.getenv('API_TOKEN', '')
MAX_BYTES = 15 * 1024 * 1024
RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '90'))
if RETENTION_DAYS < 1:
    raise ValueError('BACKUP_RETENTION_DAYS 必须为正整数')

def now():
    return datetime.now(TZ).isoformat(timespec='seconds')

def prepare():
    for folder in ('screenshots', 'backups', 'inbox', 'processed', 'failed'):
        (DATA / folder).mkdir(parents=True, exist_ok=True)
