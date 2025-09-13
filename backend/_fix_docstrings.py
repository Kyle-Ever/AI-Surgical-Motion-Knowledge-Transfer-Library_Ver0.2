from pathlib import Path
p = Path('backend/app/api/routes/videos.py')
lines = p.read_text(encoding='utf-8').splitlines()
# Safely set docstrings at known indices if within range
if len(lines) > 27:
    lines[27] = '    """Upload a video file"""'
if len(lines) > 119:
    lines[119] = '    """Get video"""'
if len(lines) > 131:
    lines[131] = '    """List videos"""'

p.write_text('\n'.join(lines), encoding='utf-8')
print('done')
