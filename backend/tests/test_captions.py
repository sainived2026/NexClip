"""Quick functional test for CaptionService."""
from app.services.caption_service import CaptionService

cs = CaptionService

# Test data — mimics real transcript issues
test_segments = [
    {"start": 0.44, "end": 3.32, "text": "France   invented   a   lot   of   early   technologies   in"},
    {"start": 3.32, "end": 7.7, "text": "the   world."},
    {"start": 22.78, "end": 24.22, "text": "I,   I,   I   think   the   missing   point"},
    {"start": 93.5, "end": 95.15, "text": "uh,   the   US   and   China."},
    {"start": 252.05, "end": 252.05, "text": "..."},
    {"start": 249.78, "end": 252.05, "text": "speech   or   violence   in   our   societies-   Sure"},
    {"start": 138.04, "end": 139.7, "text": "backend,   like-   Yeah,   I   think   so,   because   we"},
]

print("=" * 70)
print("RAW SEGMENTS:")
print("=" * 70)
for s in test_segments:
    print(f"  {s['start']:7.2f}-{s['end']:7.2f}: {s['text']}")

print()
print("=" * 70)
print("PROCESSED SEGMENTS:")
print("=" * 70)
result = cs.process_segments(test_segments)
for s in result:
    print(f"  {s['start']:7.2f}-{s['end']:7.2f}: {s['text']}")

# Test FFmpeg encoding
print()
print("=" * 70)
print("FFMPEG ENCODING TEST:")
print("=" * 70)
test_texts = [
    "Hello: World! It's a test; right?",
    "50% off [discount] {promo}",
    'He said "wow" and left',
]
for t in test_texts:
    encoded = cs.encode_for_ffmpeg(t)
    print(f"  IN:  {t}")
    print(f"  OUT: {encoded}")
    print()

# Test caption filter building
print("=" * 70)
print("CAPTION FILTER BUILD TEST:")
print("=" * 70)
filters = cs.build_caption_filters(result, 0.0, 10.0)
for f in filters:
    print(f"  {f[:120]}...")
print(f"\nTotal filters: {len(filters)}")
