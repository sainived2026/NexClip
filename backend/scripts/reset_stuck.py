from app.db.database import SessionLocal
from app.db.models import Project, ProjectStatus
from app.workers.tasks import process_video_task

db = SessionLocal()
p = db.query(Project).filter(Project.status == ProjectStatus.TRANSCRIBING).first()
if p:
    print(f"Resetting {p.id}...")
    p.status = ProjectStatus.UPLOADED
    p.progress = 5
    p.status_message = "Re-queued for processing..."
    db.commit()
    process_video_task.delay(p.id)
    print(f"Done. Re-queued project {p.id}")
else:
    print("No stuck projects found.")
db.close()
