from app.workers.tasks import process_video_task
import sqlite3
import traceback

try:
    conn = sqlite3.connect('nexclip.db')
    cursor = conn.cursor()
    # Find the most recently submitted project
    cursor.execute("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        project_id = row[0]
        print(f"Running task synchronously for project: {project_id}")
        process_video_task(project_id)
    else:
        print("No projects found in the DB.")
except Exception as e:
    print("Error executing task manually:")
    traceback.print_exc()
