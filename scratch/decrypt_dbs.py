import os
import sqlcipher3

def decrypt(db_path, password="mysecretpassword"):
    if not os.path.exists(db_path):
        print("Not found:", db_path)
        return
    with open(db_path, "rb") as f:
        header = f.read(16)
    if header == b"SQLite format 3\x00":
        print(db_path, "is already plaintext SQLite!")
        return
    
    plain_path = db_path + ".plain"
    if os.path.exists(plain_path):
        os.remove(plain_path)
    
    conn = sqlcipher3.connect(db_path)
    conn.execute(f"PRAGMA key = '{password}';")
    conn.execute(f"ATTACH DATABASE '{plain_path}' AS plaintext KEY '';")
    conn.execute("SELECT sqlcipher_export('plaintext');")
    conn.execute("DETACH DATABASE plaintext;")
    conn.close()
    
    # replace original with plain
    bak_path = db_path + ".enc_bak"
    if os.path.exists(bak_path):
        os.remove(bak_path)
    os.rename(db_path, bak_path)
    os.rename(plain_path, db_path)
    print("Successfully decrypted:", db_path)

if __name__ == "__main__":
    decrypt("databases/hierarchy.db")
    appdata = os.path.join(os.environ.get("APPDATA", ""), "Universal SQL Client", "databases", "hierarchy.db")
    decrypt(appdata)
