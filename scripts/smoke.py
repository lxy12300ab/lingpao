"""Test the local running HTTPS stack with a real screenshot. Uses .env without printing secrets."""
import json
import os
from pathlib import Path
import sys
import httpx

root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
with httpx.Client(base_url='https://localhost:'+env.get('HTTPS_PORT','8443'), verify=False,
                  headers={'X-API-Key':env['API_TOKEN']},timeout=180) as client:
    r=client.get('/api/health');r.raise_for_status();print('Health:',r.json())
    r=client.get('/');r.raise_for_status();assert 'no-store' in r.headers['cache-control']
    assert '__BUILD__' not in r.text
    if len(sys.argv)>1:
        with open(sys.argv[1],'rb') as file:
            r=client.post('/api/upload',files={'file':('sample.png',file,'image/png')},data={'captured_date':'2026-09-19'})
        r.raise_for_status()
        result=r.json();print('OCR:',json.dumps(result,ensure_ascii=False))
        assert result['status'] in ('done','done_with_warnings'),result
        assert [x['km'] for x in result['data']['daily']]==[42,73,73,75,77,73,0]
        assert len(result['data']['weekly'])==6
    r=client.get('/api/data');r.raise_for_status();print('Records:',{k:len(v) for k,v in r.json().items()})
    r=client.post('/api/admin/backup');r.raise_for_status();print('Backup:',r.json())
    assert client.get('/api/data',headers={'X-API-Key':''}).status_code==401
    print('HTTPS smoke checks passed.')
