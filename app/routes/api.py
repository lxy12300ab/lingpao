import json
import os
import secrets
import uuid
from datetime import date
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from .. import config, db, backup, service
from ..models import Dataset

def authorize(request: Request):
    raw = request.headers.get('authorization', '')
    token = request.headers.get('x-api-key') or (raw[7:] if raw.startswith('Bearer ') else '')
    if not config.TOKEN or not secrets.compare_digest(token.encode(), config.TOKEN.encode()):
        raise HTTPException(401, '请输入访问密钥', headers={'WWW-Authenticate': 'Bearer'})
    origin = request.headers.get('origin')
    if origin and origin.split('://')[-1] != request.headers.get('host'):
        raise HTTPException(403, '不允许跨站写入')

router = APIRouter(prefix='/api', dependencies=[Depends(authorize)])

@router.get('/data')
def data():
    return db.get_data()

@router.post('/upload')
async def upload(file: UploadFile = File(...), captured_date: date = Form(...)):
    # Date is mandatory: filenames and HTTP upload time cannot establish capture date.
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg','.webp'):
        raise HTTPException(415, '请上传 PNG、JPEG 或 WebP 截图')
    path = config.DATA/'screenshots'/f'{uuid.uuid4().hex}{suffix}'
    size = 0
    try:
        with path.open('wb') as out:
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size > config.MAX_BYTES:
                    raise HTTPException(413, '截图不能超过15MB')
                out.write(chunk)
        return await run_in_threadpool(service.process_file, path, captured_date)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except BlockingIOError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, '无法识别截图，请确认格式、完整性和截图日期') from exc
    except Exception as exc:
        raise HTTPException(422, 'OCR未完成，请检查识别记录和容器日志') from exc
    finally:
        await file.close()

@router.get('/screenshots')
def screenshots():
    with db.connect() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM screenshots ORDER BY id DESC LIMIT 30')]
    for row in rows:
        row['ocr_result'] = json.loads(row['ocr_result'] or '{}')
    return rows

@router.get('/screenshots/{sid}/image')
def screenshot_image(sid: int):
    with db.connect() as c:
        row = c.execute('SELECT filename FROM screenshots WHERE id=?',(sid,)).fetchone()
    if not row:
        raise HTTPException(404, '截图不存在')
    return FileResponse(config.DATA/'screenshots'/Path(row['filename']).name)

@router.post('/screenshots/{sid}/confirm')
def confirm(sid: int, dataset: Dataset):
    with db.connect() as c:
        if not c.execute('SELECT id FROM screenshots WHERE id=?',(sid,)).fetchone():
            raise HTTPException(404,'截图不存在')
    return service.review(sid, dataset)

@router.post('/admin/backup')
def manual_backup():
    return backup.create_backup()

@router.get('/admin/backups')
def backups():
    return backup.list_backups()

@router.get('/admin/backups/{filename}')
def download_backup(filename: str):
    if filename not in {b['filename'] for b in backup.list_backups()}:
        raise HTTPException(404, '备份不存在')
    return FileResponse(config.DATA/'backups'/filename, filename=filename)

@router.get('/admin/logs')
def logs():
    with db.connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM upload_log ORDER BY id DESC LIMIT 100')]
