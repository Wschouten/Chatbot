# Feature 59: Database Backup & Restore

**Effort:** ~30 min
**Status:** Todo
**Priority:** Medium (data safety — `portal.db` holds all admin portal work)
**Dependencies:** None
**Blocks:** None

---

## Problem

`backend/data/portal.db` contains all conversation metadata, notes, labels, and ratings entered via the admin portal. This SQLite database lives on a Railway volume — if that volume is lost, corrupted, or accidentally deleted, all admin portal work is gone permanently.

There is currently no backup procedure.

---

## Solution

1. Create a `scripts/backup_db.sh` script for manual on-demand backups
2. Document Railway's built-in volume snapshot capability
3. Document how to restore from backup
4. Add backup reminder to the maintenance schedule

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/backup_db.sh` | Manual backup script (local/remote) |
| `scripts/restore_db.sh` | Restore from backup script |

---

## Backup Script: `scripts/backup_db.sh`

```bash
#!/usr/bin/env bash
# backup_db.sh — create a timestamped backup of portal.db
# Usage: ./scripts/backup_db.sh [output_dir]
#
# Default output: ./backups/portal_db_<timestamp>.sqlite

set -e

DB_PATH="${PORTAL_DB_PATH:-backend/data/portal.db}"
BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/portal_db_${TIMESTAMP}.sqlite"

if [ ! -f "$DB_PATH" ]; then
    echo "Error: Database not found at $DB_PATH"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# Use SQLite's .backup command for a safe, consistent copy
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

echo "Backup saved to: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
```

Make executable: `chmod +x scripts/backup_db.sh`

---

## Restore Script: `scripts/restore_db.sh`

```bash
#!/usr/bin/env bash
# restore_db.sh — restore portal.db from a backup file
# Usage: ./scripts/restore_db.sh <backup_file>
# WARNING: This OVERWRITES the current portal.db

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sqlite>"
    exit 1
fi

BACKUP_FILE="$1"
DB_PATH="${PORTAL_DB_PATH:-backend/data/portal.db}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

read -p "This will OVERWRITE $DB_PATH. Are you sure? (y/N) " confirm
if [ "$confirm" != "y" ]; then
    echo "Aborted."
    exit 0
fi

# Backup current DB before overwriting
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
cp "$DB_PATH" "${DB_PATH}.pre-restore-${TIMESTAMP}.bak" 2>/dev/null || true

cp "$BACKUP_FILE" "$DB_PATH"
echo "Restored $BACKUP_FILE to $DB_PATH"
echo "Previous DB saved as ${DB_PATH}.pre-restore-${TIMESTAMP}.bak"
```

---

## Railway Volume Snapshots

Railway Pro plans support volume snapshots from the dashboard:

1. Railway dashboard → your service → **Volumes**
2. Click the volume → **"Create Snapshot"**
3. Snapshots can be restored via the Railway dashboard

**Recommended snapshot schedule:** Weekly (or before any major deployment)

> **Note:** Railway Hobby plan may not support manual snapshots. Check the Railway docs for current plan features.

---

## Off-Site Backup (Recommended for Production)

For additional safety, download a backup to your local machine periodically:

```bash
# Using Railway CLI
railway run sqlite3 /app/backend/data/portal.db ".backup /tmp/portal_backup.db"
railway download /tmp/portal_backup.db ./backups/portal_$(date +%Y%m%d).sqlite
```

Or use `rsync` / `scp` if you have SSH access to the Railway container.

---

## Add to `.gitignore`

```
backups/
*.bak
*.pre-restore-*.bak
```

---

## Maintenance Schedule

| Task | Frequency | Method |
|------|-----------|--------|
| Download local backup | Monthly | `./scripts/backup_db.sh` |
| Railway volume snapshot | Before major deployments | Railway dashboard |
| Verify backup integrity | Quarterly | Open backup in SQLite browser |

---

## Verification

```bash
# Create a backup
./scripts/backup_db.sh

# Verify it's a valid SQLite file
sqlite3 ./backups/portal_db_<timestamp>.sqlite "SELECT COUNT(*) FROM conversation_metadata;"
# Expected: shows conversation count (matches production)

# Test restore (on a test copy — never on production directly)
cp backend/data/portal.db /tmp/portal.db.test
PORTAL_DB_PATH=/tmp/portal.db.test ./scripts/restore_db.sh ./backups/portal_db_<timestamp>.sqlite
```
