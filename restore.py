"""Offline restore only. Stop app container; safety backup before replacing SQLite."""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from app import config

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('backup',type=Path)
    p.add_argument('--confirm-app-stopped',action='store_true',required=True)
    args=p.parse_args()
    source=args.backup.resolve()
    if source==config.DB or not source.is_file():
        p.error('请选择一个现有备份文件，不得选择当前数据库')
    conn=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    try:
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            p.error('备份完整性校验失败')
        required={'daily_mileage','weekly_energy','energy_breakdown','screenshots','upload_log','settings'}
        names={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required<=names or conn.execute('PRAGMA user_version').fetchone()[0]!=1:
            p.error('备份结构不兼容')
        config.prepare()
        stamp=datetime.now(config.TZ).strftime('%Y%m%d-%H%M%S-%f')
        if config.DB.exists():
            current=sqlite3.connect(config.DB)
            safe=config.DATA/'backups'/f'before-restore-{stamp}.db'
            dest=sqlite3.connect(safe)
            try:
                current.backup(dest)
                current.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            finally:
                dest.close();current.close()
            print(f'恢复前安全备份：{safe.name}')
        temp=config.DATA/f'restore-{stamp}.tmp'
        dest=sqlite3.connect(temp)
        try:
            conn.backup(dest)
        finally:
            dest.close()
        for suffix in ('-wal','-shm'):
            Path(str(config.DB)+suffix).unlink(missing_ok=True)
        temp.replace(config.DB)
        print('恢复完成；请启动 app。原始截图另存于 data/screenshots，不在数据库备份中。')
    finally:
        conn.close()

if __name__=='__main__':
    main()
