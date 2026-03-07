"""One-off script to sync bootstrap admin credentials in the DB (e.g. after changing .env)."""
from server.core.database import SessionLocal, init_db
from server.modules.auth.service import bootstrap_admin_user

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin_user(db)
        print("Admin credentials synced. You can log in with BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD.")
    finally:
        db.close()
