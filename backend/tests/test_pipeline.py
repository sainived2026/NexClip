"""E2E pipeline test with user's specific video URL."""
import requests
import time
import uuid

BASE = "http://localhost:8000"
unique = uuid.uuid4().hex[:8]

# Register
r = requests.post(f"{BASE}/api/auth/register", json={
    "email": f"test_{unique}@test.com",
    "username": f"test_{unique}",
    "password": "TestPass123!",
    "full_name": "Test User"
})
print("Register:", r.status_code)
data = r.json()
token = data["access_token"]

# Submit the user's specific video
VIDEO_URL = "https://youtu.be/xAt1xcC6qfM?si=2CvniDsq17gigWAg"
r = requests.post(f"{BASE}/api/projects/url",
    json={"url": VIDEO_URL, "title": "Raj Shamani Podcast", "clip_count": 10},
    headers={"Authorization": f"Bearer {token}"})
print("Submit:", r.status_code)
project_id = r.json()["id"]
print("Project:", project_id)

# Poll status — 10 minutes max (long video needs time)
for i in range(120):
    time.sleep(5)
    st = requests.get(f"{BASE}/api/projects/{project_id}/status",
        headers={"Authorization": f"Bearer {token}"}).json()
    err = st.get("error_message", "")
    print(f"[{(i+1)*5:4d}s] {st['status']:20s} {st['progress']:3d}% - {st['status_message'][:80]}", end="")
    if err:
        print(f" | ERR: {err[:80]}", end="")
    print()
    if st["status"] in ("COMPLETED", "FAILED"):
        break

# Final: check clips
if st["status"] == "COMPLETED":
    clips_r = requests.get(f"{BASE}/api/projects/{project_id}/clips",
        headers={"Authorization": f"Bearer {token}"})
    print(f"\n=== CLIPS: {clips_r.status_code} ===")
    clips_data = clips_r.json()
    print(f"Total clips: {len(clips_data)}")
    for c in clips_data:
        print(f"  Clip {c.get('rank', '?')}: {c.get('start_time', 0):.1f}-{c.get('end_time', 0):.1f}s "
              f"({c.get('duration', 0):.0f}s) score={c.get('viral_score', 0):.0f} "
              f"title=\"{c.get('title_suggestion', '')[:50]}\"")
elif st["status"] == "FAILED":
    print(f"\n=== FAILED ===")
    print(f"Error: {st.get('error_message', 'unknown')}")
