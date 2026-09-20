"""Import legacy JSON using the same merge rules; backup before writing."""
import argparse
import json
from pathlib import Path
from app import config, db, backup
from app.models import Dataset

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    legacy = json.loads(args.json_file.read_text(encoding='utf-8'))
    legacy.pop('last_update', None)  # Original static page metadata, not a business record.
    dataset = Dataset.model_validate(legacy)
    if args.dry_run:
        print(json.dumps({'daily':len(dataset.daily),'weekly':len(dataset.weekly),'energy':len(dataset.energy)}))
        return
    db.init()
    backup.create_backup()
    with db.connect() as c:
        result = db.merge(c, dataset, source='migration')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
