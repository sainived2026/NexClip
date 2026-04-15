import sys
import subprocess

cmd = [sys.executable, "-m", "yt_dlp", "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best", "--merge-output-format", "mp4", "--output", "test_video.mp4", "--no-playlist", "--no-warnings", "--socket-timeout", "30", "--retries", "5", "--extractor-retries", "3", "https://www.youtube.com/watch?v=UF8uR6Z6KLc"]
print("Running command:", cmd)

try:
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Return code:", res.returncode)
    print("STDOUT:", repr(res.stdout))
    print("STDERR:", repr(res.stderr))
except Exception as e:
    print("Exception running subprocess:", repr(e))
