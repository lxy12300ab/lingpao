"""Create private local runtime configuration; never overwrite an existing key/certificate."""
import os
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[1]
env = root/'.env'
if not env.exists():
    source = (root/'.env.example').read_text()
    source = source.replace('replace-this-with-a-random-secret-at-least-24-characters', secrets.token_urlsafe(32))
    source = source.replace('APP_UID=1000', f'APP_UID={os.getuid() if hasattr(os,"getuid") else 1000}')
    source = source.replace('APP_GID=1000', f'APP_GID={os.getgid() if hasattr(os,"getgid") else 1000}')
    fd = os.open(env, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write(source)
for name in ('data','certs'):
    (root/name).mkdir(exist_ok=True, mode=0o700)
certs=root/'certs'
if not (certs/'fullchain.pem').exists() and not (certs/'privkey.pem').exists():
    subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-days','3650',
                    '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',
                    '-keyout',str(certs/'privkey.pem'),'-out',str(certs/'fullchain.pem')], check=True)
    (certs/'privkey.pem').chmod(0o600)
elif not all((certs/n).exists() for n in ('fullchain.pem','privkey.pem')):
    raise SystemExit('证书不完整；请检查 certs/fullchain.pem 和 privkey.pem，不会覆盖现有文件。')
print('已准备 .env、data/、certs/。访问密钥保存在 .env；请勿提交到 GitHub。')
