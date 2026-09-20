import asyncio
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import config, db, tasks
from .routes.api import router

@asynccontextmanager
async def lifespan(app):
    if len(config.TOKEN) < 24 or config.TOKEN.startswith('replace-this'):
        raise RuntimeError('请在 .env 配置至少24位随机 API_TOKEN')
    db.init()
    # Interrupted OCR remains reviewable rather than silently stuck as processing.
    with db.connect() as c:
        c.execute("UPDATE screenshots SET ocr_status='failed', error_message='服务重启中断识别，请重新上传' WHERE ocr_status='processing'")
    stop = threading.Event()
    worker = None
    if os.getenv('ENABLE_SCHEDULER', '1') == '1':
        worker = threading.Thread(target=tasks.run, args=(stop,), daemon=True)
        worker.start()
    yield
    stop.set()
    if worker:
        await asyncio.to_thread(worker.join, 5)

app = FastAPI(title='零跑 C11 里程', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware('http')
async def no_cache(request, call_next):
    if int(request.headers.get('content-length', '0') or 0) > config.MAX_BYTES+1024*1024:
        return JSONResponse({'detail':'上传内容过大'}, status_code=413)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    return response

app.include_router(router)

@app.get('/api/health')
def health():
    try:
        with db.connect() as c:
            c.execute('SELECT count(*) FROM settings').fetchone()
        return {'status':'ok', 'build':config.BUILD, 'timezone':'Asia/Shanghai'}
    except Exception:
        return JSONResponse({'status':'error'}, status_code=503)

@app.get('/api/version')
def version():
    return {'build':config.BUILD}

@app.get('/')
@app.get('/index.html')
@app.get('/upload')
@app.get('/upload/')
def index():
    content = (config.ROOT/'static'/'index.html').read_text().replace('__BUILD__',config.BUILD)
    return HTMLResponse(content)

app.mount('/', StaticFiles(directory=config.ROOT/'static'), name='static')
