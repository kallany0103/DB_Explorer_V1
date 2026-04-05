import sqlite3
import sqlcipher3

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
            conn = sqlcipher3.connect(database, *args, **kwargs)
            # PRAGMA key must be provided immediately to decrypt the database
            conn.execute(f"PRAGMA key = '{password}';")
            return conn
        
        # Otherwise, fall back to standard sqlite3
        return _original_connect(database, *args, **kwargs)
    
    # Apply the monkey-patch globally
    sqlite3.connect = secure_connect
