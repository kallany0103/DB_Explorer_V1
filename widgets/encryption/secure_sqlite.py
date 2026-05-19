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
    If the database is found to be unencrypted, it is transparently encrypted in-place.
    """
    def secure_connect(database, *args, **kwargs):
        # Check if the database being connected to is our encrypted one
        # `database` could be a path string or a Path-like object
        db_str = str(database).replace("\\", "/")
        if db_str.endswith("hierarchy.db"):
            # Ensure the directory exists
            db_dir = os.path.dirname(database)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

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
                # The database is unencrypted. We need to encrypt it in-place using SQLCipher.
                temp_db = str(database) + ".tmp"
                try:
                    if os.path.exists(temp_db):
                        os.remove(temp_db)
                    os.rename(database, temp_db)
                    
                    # Connect to the unencrypted temp DB using sqlcipher3
                    cipher_conn = sqlcipher3.connect(temp_db)
                    
                    # Attach the target encrypted database
                    cipher_conn.execute(f"ATTACH DATABASE '{database}' AS encrypted KEY '{password}';")
                    # Export all tables, schemas, and data to the new encrypted database
                    cipher_conn.execute("SELECT sqlcipher_export('encrypted');")
                    cipher_conn.execute("DETACH DATABASE encrypted;")
                    cipher_conn.close()
                    
                    # Clean up the unencrypted temporary database
                    os.remove(temp_db)
                    is_unencrypted = False
                except Exception as e:
                    print(f"Failed to encrypt database in-place: {e}")
                    # If migration fails, restore the unencrypted backup if possible
                    if os.path.exists(temp_db) and not os.path.exists(database):
                        try:
                            os.rename(temp_db, database)
                        except Exception:
                            pass
                    # Fallback to unencrypted connection
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
