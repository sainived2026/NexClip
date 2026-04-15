from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.DEBUG)
print("Starting WhisperModel load...")
try:
    model = WhisperModel("medium", device="cuda", compute_type="float16")
    print("Model loaded successfully on CUDA float16!")
except Exception as e:
    print(f"Failed to load: {e}")
