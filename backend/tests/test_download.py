import os
import sys
import asyncio
from pathlib import Path

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.download_service import DownloadService

def test():
    print("Testing DownloadService...")
    service = DownloadService()
    try:
        # 9QXCkMTbrSk is the video that failed the JS challenge earlier
        result = service.download_video("https://www.youtube.com/watch?v=9QXCkMTbrSk", "test_user")
        print("Success:", result)
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test()
