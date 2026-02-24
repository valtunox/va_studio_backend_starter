python scripts/restore_database.py --backup-file app/data/backups/postgres/recruitment_latest_updated.sql
python scripts/restore_database.py --backup-file app/data/backups/postgres/recruitment_latest_updated.dump
python scripts/restore_database.py --backup-file backup.dump --clean
python scripts/restore_database.py --backup-file backup.dump --host localhost --port 5432 --database mydb --user myuser
