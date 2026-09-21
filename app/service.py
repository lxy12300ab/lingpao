import json
import logging
import threading
import uuid
import warnings
from datetime import date
from pathlib import Path
from PIL import Image
from . import config, db, ocr
from .models import Dataset

OCR_LOCK = threading.Lock()

def process_file(path: Path, captured: date):
    if not OCR_LOCK.acquire(blocking=False):
        raise BlockingIOError('正在识别另一张截图，请稍后重试')
    try:
        if captured > date.fromisoformat(config.now()[:10]):
            raise ValueError('截图日期不能晚于北京时间今天')
        if path.stat().st_size > config.MAX_BYTES:
            raise ValueError('截图不能超过15MB')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as im:
                if im.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('仅支持 PNG、JPEG、WebP')
                im.verify()
        with db.connect() as c:
            sid = c.execute('INSERT INTO screenshots(filename,uploaded_at,ocr_status) VALUES(?,?,?)',
                            (path.name, config.now(), 'processing')).lastrowid
        try:
            result = ocr.recognize(path, captured)
            dataset = Dataset(**result['data'])
            status = 'review' if result['warnings'] else 'done'
            with db.connect() as c:
                # When any section is ambiguous, keep the whole proposal for explicit review.
                merged = None if result['warnings'] else db.merge(c, dataset, sid)
                if merged and merged['rejected']:
                    status = 'done_with_warnings'
                result['merge'] = merged
                c.execute('UPDATE screenshots SET ocr_status=?,ocr_result=? WHERE id=?',
                          (status, json.dumps(result,ensure_ascii=False), sid))
                db.log(c, 'upload', sid, status, '; '.join(result['warnings']))
            return {'id': sid, 'status': status, **result}
        except Exception as exc:
            logging.getLogger(__name__).exception('OCR failed for screenshot %s', sid)
            with db.connect() as c:
                c.execute('UPDATE screenshots SET ocr_status=?,error_message=? WHERE id=?',
                          ('failed', '识别失败，请检查截图完整性及OCR日志', sid))
                db.log(c, 'upload', sid, 'failed', type(exc).__name__)
            raise
    finally:
        OCR_LOCK.release()

def review(sid, dataset):
    with db.connect() as c:
        result = db.merge(c, dataset, sid, source='review')
        row = c.execute('SELECT ocr_result,ocr_status FROM screenshots WHERE id=?', (sid,)).fetchone()
        if not row:
            raise LookupError('截图不存在')
        if row['ocr_status'] == 'dismissed':
            # The exception rolls back the merge in this write transaction.
            raise ValueError('此截图已忽略，请先恢复待核对')
        payload = json.loads(row['ocr_result'] or '{}')
        payload['confirmed_data'] = dataset.model_dump(mode='json')
        payload['merge'] = result
        c.execute('UPDATE screenshots SET ocr_status=?,ocr_result=? WHERE id=?',
                  ('confirmed', json.dumps(payload,ensure_ascii=False), sid))
        return result
