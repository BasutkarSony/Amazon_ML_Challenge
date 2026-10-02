import sqlite3

conn = sqlite3.connect("candidate_index.db")

print("TABLE:")
print(
    conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='records'"
    ).fetchone()[0]
)

print("\nINDEXES:")
print(
    conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND tbl_name='records'"
    ).fetchall()
)

conn.close()
