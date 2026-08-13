import os

for path in [
    "databases/hierarchy.db",
    "databases/hierarchy.db.bak",
    os.path.join(os.environ.get("APPDATA", ""), "Universal SQL Client", "databases", "hierarchy.db")
]:
    if os.path.exists(path):
        with open(path, "rb") as f:
            header = f.read(64)
            print(f"{path}: len={os.path.getsize(path)}, header={header[:32]}")
