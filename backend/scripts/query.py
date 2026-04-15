import sqlite3

conn = sqlite3.connect('nexclip.db')
cur = conn.cursor()

# Get the last project
cur.execute("SELECT id, status, status_message FROM projects ORDER BY created_at DESC LIMIT 1")
project = cur.fetchone()

if project:
    pid = project[0]
    print(f"Project ID: {pid}")
    print(f"Status: {project[1]}")
    print(f"Message: {project[2]}")
    
    cur.execute("SELECT COUNT(*) FROM clips WHERE project_id=?", (pid,))
    count = cur.fetchone()[0]
    print(f"Generated Clips: {count}")
else:
    print("No projects found.")
