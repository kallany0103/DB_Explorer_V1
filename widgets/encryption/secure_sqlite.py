import sqlite3
import sqlcipher3
import os

# Keep a reference to the original standard sqlite3.connect function
_original_connect = sqlite3.connect

def enable_transparent_encryption(password: str):
    """
    Monkey-patches sqlite3.connect so that attempts to connect to 
    hierarchy.db are automatically intercepted and routed through sqlcipher3
    with the provided password, while all other SQLite connections remain unchanged.
    """
    def secure_connect(database, *args, **kwargs):
        # Check if the database being connected to is our encrypted one
        # `database` could be a path string or a Path-like object
        db_str = str(database).replace("\\", "/")
        if db_str.endswith("hierarchy.db"):
            is_unencrypted = False
            try:
                if os.path.exists(database):
                    with open(database, 'rb') as f:
                        header = f.read(16)
                    if header == b"SQLite format 3\x00":
                        is_unencrypted = True
            except Exception:
                pass

            if is_unencrypted:
                return _original_connect(database, *args, **kwargs)

            try:
                conn = sqlcipher3.connect(database, *args, **kwargs)
                # PRAGMA key must be provided immediately to decrypt the database
                conn.execute(f"PRAGMA key = '{password}';")
                # Test the connection to ensure it's actually an encrypted database that matches the key
                conn.execute("SELECT count(*) FROM sqlite_master;")
                return conn
            except sqlcipher3.DatabaseError:
                # If it fails, fallback to unencrypted (should rarely occur if file exists)
                return _original_connect(database, *args, **kwargs)
        
        # Otherwise, fall back to standard sqlite3
        return _original_connect(database, *args, **kwargs)
    
    # Apply the monkey-patch globally
    sqlite3.connect = secure_connect
