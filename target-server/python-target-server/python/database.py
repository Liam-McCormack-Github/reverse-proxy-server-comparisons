import sqlite3
import bcrypt
from simple_logger import log

class Database:
    def __init__(self, db_file="users.db") -> None:
        try:
            self.conn = sqlite3.connect(db_file)
            self.cursor = self.conn.cursor()
            self.create_table()
        except sqlite3.Error as e:
            log("ERROR", "Database connection failed", extras=f"DB: '{db_file}', Error: {e}")
            self.conn = None

    def create_table(self) -> None:
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS proxy_users (
            admin_id TEXT PRIMARY KEY,
            admin_secret_hash TEXT NOT NULL
        )
        """)
        self.conn.commit()

    def add_user(self, admin_id, admin_secret) -> None:
        if not self.conn:
            return False
        hashed_secret = bcrypt.hashpw(admin_secret.encode('utf-8'), bcrypt.gensalt())
        try:
            self.cursor.execute("INSERT OR REPLACE INTO proxy_users (admin_id, admin_secret_hash) VALUES (?, ?)", (admin_id, hashed_secret))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            log("ERROR", f"Failed to add admin user", extras=f"Admin ID: '{admin_id}', Error: {e}")
            return False

    def verify_user(self, admin_id, admin_secret) -> None:
        if not self.conn or not admin_id or not admin_secret:
            return False
        try:
            self.cursor.execute("SELECT admin_secret_hash FROM proxy_users WHERE admin_id = ?", (admin_id,))
            result = self.cursor.fetchone()
            if result:
                stored_hash = result[0]
                return bcrypt.checkpw(admin_secret.encode('utf-8'), stored_hash)
        except sqlite3.Error as e:
            log("ERROR", f"Failed to verify admin user", extras=f"Admin ID: '{admin_id}', Error: {e}")
        return False

    def close(self) -> None:
        if self.conn:
            self.conn.close()