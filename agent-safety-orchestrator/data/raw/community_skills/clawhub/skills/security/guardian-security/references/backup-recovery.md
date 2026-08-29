# Backup & Recovery — Reference Guide

Ensuring critical systems and data can be recovered. What to back up,
how to back it up, and how to verify backups work.

---

## 1. WHAT NEEDS TO BE BACKED UP

### Backup Priority Matrix
```
TIER 1 — CRITICAL (back up daily):
  Product files (final PDFs of all products)
  Source files for products (PSD, Figma, Word documents)
  Database files (SQLite databases with transaction history)
  Code repositories (GitHub — already backed up via git)
  
TIER 2 — IMPORTANT (back up weekly):
  Email templates and sequences
  Airtable data exports
  Configuration files and settings
  
TIER 3 — USEFUL (back up monthly):
  Marketing assets (cover images, social graphics)
  Documentation and SOPs
  Analytics data exports
```

---

## 2. BACKUP PROCEDURES

### Product Files
```
WHAT: Final PDF files for all products
WHERE TO STORE:
  Primary: Local machine (Joshua's Mac mini)
  Backup 1: GitHub (private repo for product files)
  Backup 2: Cloud storage (iCloud, Google Drive, or Dropbox)

PROCESS:
  After any product update:
  1. Save to local folder: ~/products/[product-name]/
  2. Commit to GitHub: git add -A && git commit -m "Update [product] v1.2"
  3. Verify file in GitHub
```

### Database Backup
```python
# Run this daily for any SQLite databases
import shutil
import gzip
from pathlib import Path
from datetime import datetime

def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{db_path.stem}_{timestamp}.db.gz"
    backup_path = backup_dir / backup_name
    
    with open(db_path, 'rb') as f_in:
        with gzip.open(backup_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    # Keep only last 30 days
    for old in sorted(backup_dir.glob(f"{db_path.stem}_*.db.gz"))[:-30]:
        old.unlink()
    
    return backup_path
```

---

## 3. BACKUP VERIFICATION

### The Backup is Worthless If It Doesn't Restore
```
MONTHLY BACKUP TEST:
  1. Take a backup
  2. Restore to a different location/name
  3. Verify the restored data is complete and readable
  4. Document: "Backup verified on [date]"

TESTING PRODUCT FILES:
  1. Download backup copy to a fresh folder
  2. Open the PDF — does it open?
  3. Verify page count matches current version
  4. Is it the correct version? (Not an old one?)

TESTING DATABASE BACKUPS:
  1. Restore backup to temp file
  2. Open with SQLite browser or script
  3. Run: SELECT COUNT(*) FROM products; (should return expected count)
  4. Verify most recent records are present
```

---

## 4. DISASTER RECOVERY SCENARIOS

### If We Lose All Local Files
```
RECOVERY PATH:
  1. GitHub repo → code and committed product files
  2. Gumroad → current product files (download our own products)
  3. Cloud storage backup → any non-GitHub backed up files
  
RECOVERY TIME: Hours to 1 day
PREVENTION: Regular commits + cloud backup
```

### If Gumroad Account Is Lost
```
WHAT WE LOSE: Customer data, sales history, reviews
WHAT WE KEEP: Product files, listing copy (if documented), customer emails (if backed up)

PREVENTION:
  1. Export customer emails monthly from Gumroad
  2. Keep product files in our own backup
  3. Document all listing content in our GitHub repo
  4. Have Stripe as separate payment backup
```

---

## 5. BACKUP CHECKLIST

```
WEEKLY:
- [ ] Product files backed up to GitHub
- [ ] Database backup created and stored

MONTHLY:
- [ ] Backup restoration tested (at least one file type)
- [ ] Gumroad customer list exported and stored
- [ ] All product files verified in backup locations

QUARTERLY:
- [ ] Full backup audit: what exists, where, how current?
- [ ] Recovery scenario test: can we restore from backup in < 4 hours?
```
