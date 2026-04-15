from app.db.database import SessionLocal
from app.db.models import Clip, Project
db = SessionLocal()
proj = db.query(Project).filter(Project.title.like('%ClipAura%')).first()
if proj:
    print(f"Project: {proj.title} ({proj.id})")
    clips = db.query(Clip).filter(Clip.project_id == proj.id).all()
    print(f"Total clips in DB: {len(clips)}")
    for c in clips:
        cap = c.captioned_video_url or "NONE"
        land = c.file_path_landscape or "NONE"
        title = (c.title_suggestion or "untitled")[:50]
        print(f"  Rank {c.rank}: {title}")
        print(f"    path={c.file_path}")
        print(f"    captioned={cap}")
        print(f"    landscape={land}")
        print(f"    caption_status={c.caption_status}")
        print()
else:
    print("No project found")
db.close()
