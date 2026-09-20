"""Create a source-only ZIP: explicit allowlist excludes tokens, certificates and all private data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
target=root.parent/'leap-mileage-source.zip'
files=['Dockerfile','docker-compose.yml','requirements.txt','requirements-dev.txt','.env.example',
       '.gitignore','.dockerignore','migrate.py','restore.py','README.md','DEPLOY.md','VALIDATION.md','data.sample.json']
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root/name,'leap-mileage/'+name)
    for folder in ('app','nginx','scripts','tests'):
        for path in sorted((root/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.name!='.htpasswd':
                archive.write(path,'leap-mileage/'+str(path.relative_to(root)))
print(target)
