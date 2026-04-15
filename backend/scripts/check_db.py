import sqlite3
c = sqlite3.connect("nexclip.db")
r = c.execute("SELECT v.file_path, v.source_url, p.status, p.error_message FROM videos v JOIN projects p ON p.id=v.project_id ORDER BY p.created_at DESC LIMIT 3")
for row in r.fetchall():
    print(row)
c.close()
